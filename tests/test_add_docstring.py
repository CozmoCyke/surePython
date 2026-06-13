from __future__ import annotations

import subprocess
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import surepython.codemods as codemods
from surepython.cli import main
from surepython.codemods import add_docstring
from surepython.datasette_log import read_last_operation
from surepython.git_tools import GitError


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_module.py"


def init_git_repo(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "surepython@example.com"], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "SurePython"], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "baseline"], cwd=str(root), check=True, capture_output=True, text=True)


def write_fixture_file(root: Path, content: str | None = None) -> Path:
    sample = root / "sample.py"
    sample.write_text(content or FIXTURE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    return sample


def git_status_short(root: Path) -> str:
    completed = subprocess.run(
        ["git", "status", "--short"],
        cwd=str(root),
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _never_called(_: Path, __: str | None = None) -> tuple[int, str]:
    raise AssertionError("pytest should not run")


def read_db_rows(db_path: Path) -> list[tuple]:
    with sqlite3.connect(str(db_path)) as connection:
        return connection.execute(
            """
            SELECT created_at, project_path, file_path, operation, symbol, before_sha256,
                   after_sha256, git_diff, pytest_command, pytest_exit_code, pytest_status,
                   status, message
            FROM surepython_operations
            ORDER BY id
            """
        ).fetchall()


def test_add_docstring_inserts_skeleton_for_global_function(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = root / "sample.py"
    sample.write_text("def run_audit():\n    return 1\n", encoding="utf-8")
    init_git_repo(root)

    result = add_docstring(sample, "run_audit", project_root=root)

    assert '"""TODO: Document this function."""' in sample.read_text(encoding="utf-8")
    assert result.symbol == "run_audit"
    assert result.status == "applied"
    assert "1 file changed" in result.git_stat or result.git_stat.strip() != ""
    assert result.logged is False
    assert result.operation_id is None

    record = read_last_operation()
    assert record.operation == "add-docstring"
    assert record.symbol == "run_audit"


def test_add_docstring_inserts_skeleton_for_class_method(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_fixture_file(root)
    init_git_repo(root)

    result = add_docstring(sample, "SampleClass.sample_method", project_root=root)
    updated = sample.read_text(encoding="utf-8")

    assert result.symbol == "SampleClass.sample_method"
    assert result.status == "applied"
    assert updated.count('"""TODO: Document this function."""') == 1
    assert 'def sample_method():\n    return "global"\n' in updated
    assert (
        'class SampleClass:\n    def sample_method(self):\n        """TODO: Document this function."""\n        return "class"\n'
        in updated
    )
    assert 'class OtherClass:\n    def sample_method(self):\n        return "other"\n' in updated


def test_run_pytest_uses_python_m_pytest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    init_git_repo(root)
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append(args)
        assert kwargs["cwd"] == str(root)
        assert kwargs["check"] is False
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(codemods.subprocess, "run", fake_run)

    exit_code, output = codemods.run_pytest(root)

    assert exit_code == 0
    assert output == "ok"
    assert calls == [[codemods.sys.executable, "-m", "pytest"]]


def test_add_docstring_with_test_runs_pytest_and_reports_success(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_fixture_file(root)
    init_git_repo(root)
    calls: list[Path] = []

    def fake_run_pytest(cwd: Path, command: str | None = None) -> tuple[int, str]:
        calls.append(cwd)
        assert command is None
        return 0, "collected 1 item"

    monkeypatch.setattr(codemods, "run_pytest", fake_run_pytest)

    result = add_docstring(sample, "SampleClass.sample_method", project_root=root, run_tests=True)

    assert calls == [root]
    assert result.status == "tested"
    assert result.pytest_status == "passed"
    assert result.pytest_exit_code == 0
    assert result.pytest_command == f"{codemods.sys.executable} -m pytest"
    assert '"""TODO: Document this function."""' in sample.read_text(encoding="utf-8")


def test_add_docstring_with_db_logs_operation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_fixture_file(root)
    init_git_repo(root)
    db_path = root / "surepython_lab.db"

    exit_code = main(
        [
            "add-docstring",
            str(sample),
            "--function",
            "SampleClass.sample_method",
            "--db",
            str(db_path),
        ]
    )

    assert exit_code == 0
    rows = read_db_rows(db_path)
    assert len(rows) == 1
    row = rows[0]
    assert row[3] == "add-docstring"
    assert row[4] == "SampleClass.sample_method"
    assert row[11] == "applied"
    assert row[6] is not None
    assert row[7]
    assert read_last_operation().operation_id is not None


def test_add_docstring_with_test_and_db_logs_pytest_status(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_fixture_file(root)
    init_git_repo(root)
    db_path = root / "surepython_lab.db"
    monkeypatch.setattr(codemods, "run_pytest", lambda cwd, command=None: (0, "ok"))

    result = add_docstring(sample, "SampleClass.sample_method", project_root=root, db_path=db_path, run_tests=True)

    rows = read_db_rows(db_path)
    assert len(rows) == 1
    row = rows[0]
    assert row[8] == f"{codemods.sys.executable} -m pytest"
    assert row[9] == 0
    assert row[10] == "passed"
    assert row[11] == "tested"
    assert result.pytest_status == "passed"
    assert result.operation_id is not None
    assert result.logged is True


def test_add_docstring_without_db_keeps_previous_behavior(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_fixture_file(root)
    init_git_repo(root)
    db_path = root / "surepython_lab.db"

    result = add_docstring(sample, "SampleClass.sample_method", project_root=root)

    assert result.db_path is None
    assert not db_path.exists()


def test_add_docstring_dry_run_with_db_does_not_log_to_sqlite_or_write_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_fixture_file(root)
    original = sample.read_text(encoding="utf-8")
    init_git_repo(root)
    db_path = root / "surepython_lab.db"

    result = add_docstring(
        sample,
        "SampleClass.sample_method",
        project_root=root,
        db_path=db_path,
        dry_run=True,
    )

    assert not db_path.exists()
    assert sample.read_text(encoding="utf-8") == original
    assert result.status == "planned"
    assert result.logged is False
    assert result.operation_id is None


def test_add_docstring_refusal_keeps_sqlite_empty_when_db_provided(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_fixture_file(
        root,
        FIXTURE_PATH.read_text(encoding="utf-8").replace(
            '    def sample_method(self):\n        return "class"\n',
            '    def sample_method(self):\n        """Existing."""\n        return "class"\n',
        ),
    )
    init_git_repo(root)
    db_path = root / "surepython_lab.db"

    try:
        add_docstring(sample, "SampleClass.sample_method", project_root=root, db_path=db_path)
    except GitError:
        pass
    else:
        raise AssertionError("Expected refusal")

    assert not db_path.exists()
    assert "docstring" in str(read_last_operation().message or "").lower()


def test_add_docstring_with_test_propagates_pytest_failure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_fixture_file(root)
    init_git_repo(root)

    monkeypatch.setattr(codemods, "run_pytest", lambda cwd, command=None: (3, "pytest failed"))

    result = add_docstring(sample, "SampleClass.sample_method", project_root=root, run_tests=True)

    assert result.status == "failed"
    assert result.pytest_status == "failed"
    assert result.pytest_exit_code == 3
    assert result.pytest_command == f"{codemods.sys.executable} -m pytest"


def test_add_docstring_without_test_leaves_runner_unused(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_fixture_file(root)
    init_git_repo(root)
    monkeypatch.setattr(codemods, "run_pytest", _never_called)

    result = add_docstring(sample, "SampleClass.sample_method", project_root=root)

    assert result.status == "applied"
    assert result.pytest_command is None
    assert result.pytest_exit_code is None


def test_add_docstring_dry_run_does_not_modify_file_and_shows_preview(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_fixture_file(root)
    original = sample.read_text(encoding="utf-8")
    init_git_repo(root)
    monkeypatch.setattr(codemods, "run_pytest", _never_called)

    exit_code = main(
        [
            "add-docstring",
            str(sample),
            "--function",
            "SampleClass.sample_method",
            "--dry-run",
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Dry run; no files changed." in output
    assert "Preview diff:" in output
    assert '"""TODO: Document this function."""' in output
    assert sample.read_text(encoding="utf-8") == original
    assert git_status_short(root) == ""


def test_add_docstring_dry_run_with_test_does_not_run_pytest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_fixture_file(root)
    init_git_repo(root)
    monkeypatch.setattr(codemods, "run_pytest", _never_called)

    result = add_docstring(sample, "SampleClass.sample_method", project_root=root, run_tests=True, dry_run=True)

    assert result.status == "planned"
    assert result.pytest_command is None
    assert result.pytest_exit_code is None


def test_add_docstring_dry_run_refuses_existing_docstring(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_fixture_file(
        root,
        FIXTURE_PATH.read_text(encoding="utf-8").replace(
            '    def sample_method(self):\n        return "class"\n',
            '    def sample_method(self):\n        """Existing."""\n        return "class"\n',
        ),
    )
    init_git_repo(root)

    try:
        add_docstring(sample, "SampleClass.sample_method", project_root=root, dry_run=True)
    except GitError as exc:
        assert "docstring" in str(exc).lower()
    else:
        raise AssertionError("Expected refusal")


def test_add_docstring_refuses_existing_docstring_in_class_method(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_fixture_file(
        root,
        FIXTURE_PATH.read_text(encoding="utf-8").replace(
            '    def sample_method(self):\n        return "class"\n',
            '    def sample_method(self):\n        """Existing."""\n        return "class"\n',
        ),
    )
    init_git_repo(root)

    try:
        add_docstring(sample, "SampleClass.sample_method", project_root=root)
    except GitError as exc:
        assert "docstring" in str(exc).lower()
    else:
        raise AssertionError("Expected refusal")


def test_add_docstring_refuses_unknown_class(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_fixture_file(root)
    init_git_repo(root)

    try:
        add_docstring(sample, "MissingClass.sample_method", project_root=root)
    except GitError as exc:
        assert "not found" in str(exc).lower()
    else:
        raise AssertionError("Expected refusal")


def test_add_docstring_refuses_unknown_method(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_fixture_file(root)
    init_git_repo(root)

    try:
        add_docstring(sample, "SampleClass.missing_method", project_root=root)
    except GitError as exc:
        assert "not found" in str(exc).lower()
    else:
        raise AssertionError("Expected refusal")


def test_add_docstring_refuses_ambiguous_unqualified_method_name(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_fixture_file(root)
    init_git_repo(root)

    try:
        add_docstring(sample, "sample_method", project_root=root)
    except GitError as exc:
        assert "ambiguous" in str(exc).lower()
    else:
        raise AssertionError("Expected refusal")
