from __future__ import annotations

import hashlib
import sqlite3
import subprocess
from pathlib import Path

import pytest

import surepython.codemods as codemods
from surepython.cli import main
from surepython.codemods import add_docstring, add_return_type
from surepython.git_tools import GitError
from surepython.rollback import rollback_last


def init_git_repo(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "surepython@example.com"], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "SurePython"], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "baseline"], cwd=str(root), check=True, capture_output=True, text=True)


def commit_all(root: Path, message: str) -> None:
    subprocess.run(["git", "add", "."], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", message], cwd=str(root), check=True, capture_output=True, text=True)


def git_status_short(root: Path) -> str:
    completed = subprocess.run(
        ["git", "status", "--short"],
        cwd=str(root),
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_rows(db_path: Path) -> list[tuple]:
    with sqlite3.connect(str(db_path)) as connection:
        return connection.execute(
            """
            SELECT operation, status, symbol, before_sha256, after_sha256, pytest_status, message
            FROM surepython_operations
            ORDER BY id
            """
        ).fetchall()


def write_sample(root: Path, content: str) -> Path:
    sample = root / "sample.py"
    sample.write_text(content, encoding="utf-8")
    return sample


def test_add_return_type_to_simple_function(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user():\n    return 'user'\n")
    init_git_repo(root)

    result = add_return_type(sample, "load_user", "str", project_root=root)

    assert result.status == "applied"
    assert result.symbol == "load_user"
    assert "def load_user() -> str:" in sample.read_text(encoding="utf-8")


def test_add_return_type_to_qualified_method_only(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(
        root,
        "class UserService:\n"
        "    def load_user(self):\n"
        "        return None\n\n"
        "class OtherService:\n"
        "    def load_user(self):\n"
        "        return None\n\n"
        "def load_user():\n"
        "    return None\n",
    )
    init_git_repo(root)

    add_return_type(sample, "UserService.load_user", "User | None", project_root=root)
    updated = sample.read_text(encoding="utf-8")

    assert "def load_user(self) -> User | None:" in updated
    assert "class OtherService:\n    def load_user(self):" in updated
    assert "\ndef load_user():\n" in updated


def test_add_return_type_refuses_ambiguous_unqualified_method(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(
        root,
        "class A:\n    def load(self):\n        return 1\n\n"
        "class B:\n    def load(self):\n        return 2\n",
    )
    init_git_repo(root)

    with pytest.raises(GitError, match="ambiguous"):
        add_return_type(sample, "load", "int", project_root=root)


def test_add_return_type_supports_async_function(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "async def fetch():\n    return 'ok'\n")
    init_git_repo(root)

    add_return_type(sample, "fetch", "str", project_root=root)

    assert "async def fetch() -> str:" in sample.read_text(encoding="utf-8")


@pytest.mark.parametrize("annotation", ["str", "list[str]", "User | None"])
def test_add_return_type_accepts_supported_annotation_shapes(
    tmp_path: Path, monkeypatch, annotation: str
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user():\n    return None\n")
    init_git_repo(root)

    add_return_type(sample, "load_user", annotation, project_root=root)

    assert f"def load_user() -> {annotation}:" in sample.read_text(encoding="utf-8")


def test_add_return_type_refuses_existing_return_annotation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user() -> str:\n    return 'user'\n")
    init_git_repo(root)

    with pytest.raises(GitError, match="already has a return annotation"):
        add_return_type(sample, "load_user", "object", project_root=root)


@pytest.mark.parametrize("annotation", ["", "list["])
def test_add_return_type_refuses_invalid_annotation(
    tmp_path: Path, monkeypatch, annotation: str
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user():\n    return None\n")
    init_git_repo(root)

    with pytest.raises(GitError):
        add_return_type(sample, "load_user", annotation, project_root=root)


def test_add_return_type_refuses_missing_target(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user():\n    return None\n")
    init_git_repo(root)

    with pytest.raises(GitError, match="Target symbol not found"):
        add_return_type(sample, "missing", "str", project_root=root)


def test_add_return_type_dry_run_does_not_write_and_shows_preview(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user():\n    return None\n")
    init_git_repo(root)
    before = sample.read_text(encoding="utf-8")

    exit_code = main(
        [
            "add-return-type",
            str(sample),
            "--function",
            "load_user",
            "--annotation",
            "str",
            "--dry-run",
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Preview diff:" in output
    assert "+def load_user() -> str:" in output
    assert sample.read_text(encoding="utf-8") == before
    assert git_status_short(root) == ""


def test_add_return_type_with_test_reports_success(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user():\n    return None\n")
    init_git_repo(root)
    monkeypatch.setattr(codemods, "run_pytest", lambda cwd, command=None: (0, "ok"))

    result = add_return_type(sample, "load_user", "str | None", project_root=root, run_tests=True)

    assert result.status == "tested"
    assert result.pytest_status == "passed"


def test_add_return_type_logs_sqlite_record(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user():\n    return None\n")
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"

    result = add_return_type(sample, "load_user", "str | None", project_root=root, db_path=db_path)

    row = read_rows(db_path)[0]
    assert row[0] == "add-return-type"
    assert row[1] == "applied"
    assert row[2] == "load_user"
    assert row[3]
    assert row[4]
    assert result.operation_id is not None
    assert result.logged is True


def test_add_return_type_rollback_restores_lf_bytes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = root / "sample.py"
    original = b"def load_user():\n    return None\n"
    sample.write_bytes(original)
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"

    add_return_type(sample, "load_user", "str | None", project_root=root, db_path=db_path)
    commit_all(root, "annotate")
    rollback_last(db_path)

    assert sample.read_bytes() == original
    assert read_rows(db_path)[-1][:3] == ("rollback", "rolled_back", "load_user")


def test_add_return_type_rollback_restores_crlf_bytes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = root / "sample.py"
    original = b"def load_user():\r\n    return None\r\n"
    sample.write_bytes(original)
    init_git_repo(root)
    db_path = root / "surepython.db"

    add_return_type(sample, "load_user", "str | None", project_root=root, db_path=db_path)
    commit_all(root, "annotate")
    rollback_last(db_path)

    assert sample.read_bytes() == original


def test_add_return_type_rollback_restores_bom_bytes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = root / "sample.py"
    original = b"\xef\xbb\xbfdef load_user():\r\n    return None\r\n"
    sample.write_bytes(original)
    init_git_repo(root)
    db_path = root / "surepython.db"

    add_return_type(sample, "load_user", "str | None", project_root=root, db_path=db_path)
    commit_all(root, "annotate")
    rollback_last(db_path)

    assert sample.read_bytes() == original


def test_add_return_type_rollback_refuses_hash_mismatch_without_writing(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user():\n    return None\n")
    init_git_repo(root)
    db_path = tmp_path / "surepython_hash_mismatch.db"

    add_return_type(sample, "load_user", "str | None", project_root=root, db_path=db_path)
    commit_all(root, "annotate")
    before = sample.read_bytes()
    with sqlite3.connect(str(db_path)) as connection:
        connection.execute(
            "UPDATE surepython_operations SET before_sha256 = ? WHERE operation = ?",
            ("0" * 64, "add-return-type"),
        )
        connection.commit()

    with pytest.raises(GitError, match="before_sha256"):
        rollback_last(db_path)
    assert sample.read_bytes() == before


def test_add_return_type_cli_logs_and_runs_tests(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user():\n    return None\n")
    init_git_repo(root)
    db_path = root / "surepython.db"
    monkeypatch.setattr(codemods, "run_pytest", lambda cwd, command=None: (0, "ok"))

    exit_code = main(
        [
            "add-return-type",
            str(sample),
            "--function",
            "load_user",
            "--annotation",
            "str | None",
            "--test",
            "--db",
            str(db_path),
        ]
    )

    assert exit_code == 0
    row = read_rows(db_path)[0]
    assert row[0] == "add-return-type"
    assert row[1] == "tested"
    assert row[5] == "passed"
    assert row[2] == "load_user"


def test_add_docstring_still_works_after_phase_2_changes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def run_audit():\n    return 1\n")
    init_git_repo(root)

    result = add_docstring(sample, "run_audit", project_root=root)

    assert result.status == "applied"
    assert '"""TODO: Document this function."""' in sample.read_text(encoding="utf-8")


def test_add_return_type_smoke_hashes_crlf_round_trip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = root / "sample.py"
    original = b"def load_user():\r\n    return None\r\n"
    sample.write_bytes(original)
    init_git_repo(root)
    db_path = root / "surepython.db"
    before_sha = sha256_bytes(original)

    add_return_type(sample, "load_user", "str | None", project_root=root, db_path=db_path)
    commit_all(root, "annotate")
    result = rollback_last(db_path)

    assert result.status == "rolled_back"
    assert sha256_bytes(sample.read_bytes()) == before_sha
