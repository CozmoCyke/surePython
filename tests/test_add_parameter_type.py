from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

import surepython.codemods as codemods
from surepython.cli import main
from surepython.codemods import add_parameter_type
from surepython.git_tools import GitError
from surepython.rollback import rollback_by_id, rollback_last


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


def read_rows(db_path: Path) -> list[tuple]:
    with sqlite3.connect(str(db_path)) as connection:
        return connection.execute(
            """
            SELECT operation, status, symbol, parameter, before_sha256, after_sha256, pytest_status, source_operation_id
            FROM surepython_operations
            ORDER BY id
            """
        ).fetchall()


def latest_operation_id(db_path: Path) -> int:
    with sqlite3.connect(str(db_path)) as connection:
        row = connection.execute("SELECT id FROM surepython_operations ORDER BY id DESC LIMIT 1").fetchone()
    assert row is not None
    return int(row[0])


def write_sample(root: Path, content: str) -> Path:
    sample = root / "sample.py"
    sample.write_text(content, encoding="utf-8")
    return sample


def write_bytes_sample(root: Path, content: bytes) -> Path:
    sample = root / "sample.py"
    sample.write_bytes(content)
    return sample


def test_add_parameter_type_to_simple_function(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user(source):\n    return source\n")
    init_git_repo(root)

    result = add_parameter_type(sample, "load_user", "source", "str", project_root=root)

    assert result.status == "applied"
    assert "def load_user(source: str):" in sample.read_text(encoding="utf-8")


def test_add_parameter_type_to_method_only(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(
        root,
        "def load_user(source):\n"
        "    return source\n\n"
        "class UserService:\n"
        "    def load_user(self, source):\n"
        "        return source\n\n"
        "class OtherService:\n"
        "    def load_user(self, source):\n"
        "        return source\n",
    )
    init_git_repo(root)

    add_parameter_type(sample, "UserService.load_user", "source", "User", project_root=root)
    updated = sample.read_text(encoding="utf-8")

    assert "def load_user(source):" in updated
    assert "def load_user(self, source: User):" in updated
    assert "class OtherService:\n    def load_user(self, source):" in updated


def test_add_parameter_type_supports_async_function(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "async def fetch(source):\n    return source\n")
    init_git_repo(root)

    add_parameter_type(sample, "fetch", "source", "str", project_root=root)

    assert "async def fetch(source: str):" in sample.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("source", "target", "parameter", "annotation", "expected"),
    [
        ("def f(value=10):\n    return value\n", "f", "value", "str", "def f(value: str=10):"),
        ("def f(value, /):\n    return value\n", "f", "value", "str", "def f(value: str, /):"),
        ("def f(*, value):\n    return value\n", "f", "value", "str", "def f(*, value: str):"),
        ("class Parser:\n    @classmethod\n    def parse(cls, source):\n        return source\n", "Parser.parse", "cls", "type[Parser]", "def parse(cls: type[Parser], source):"),
        ("class Parser:\n    @classmethod\n    def parse(cls, source):\n        return source\n", "Parser.parse", "source", "str | None", "def parse(cls, source: str | None):"),
        ("def f(value):\n    return value\n", "f", "value", "\"User\"", "def f(value: \"User\"):" ),
    ],
)
def test_add_parameter_type_preserves_signature_shapes(
    tmp_path: Path, monkeypatch, source: str, target: str, parameter: str, annotation: str, expected: str
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, source)
    init_git_repo(root)

    add_parameter_type(sample, target, parameter, annotation, project_root=root)

    assert expected in sample.read_text(encoding="utf-8")


def test_add_parameter_type_refuses_existing_annotation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user(source: str):\n    return source\n")
    init_git_repo(root)

    with pytest.raises(GitError, match="already has an annotation"):
        add_parameter_type(sample, "load_user", "source", "str", project_root=root)


@pytest.mark.parametrize("annotation", ["", "list[", "dict[str"])
def test_add_parameter_type_refuses_invalid_annotation(
    tmp_path: Path, monkeypatch, annotation: str
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user(source):\n    return source\n")
    init_git_repo(root)

    with pytest.raises(GitError):
        add_parameter_type(sample, "load_user", "source", annotation, project_root=root)


def test_add_parameter_type_refuses_missing_parameter(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user(source):\n    return source\n")
    init_git_repo(root)

    with pytest.raises(GitError, match="Target parameter not found"):
        add_parameter_type(sample, "load_user", "missing", "str", project_root=root)


def test_add_parameter_type_refuses_missing_symbol(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user(source):\n    return source\n")
    init_git_repo(root)

    with pytest.raises(GitError, match="Target symbol not found"):
        add_parameter_type(sample, "missing", "source", "str", project_root=root)


def test_add_parameter_type_refuses_ambiguous_symbol(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(
        root,
        "class A:\n    def load(self, source):\n        return source\n\n"
        "class B:\n    def load(self, source):\n        return source\n",
    )
    init_git_repo(root)

    with pytest.raises(GitError, match="ambiguous"):
        add_parameter_type(sample, "load", "source", "str", project_root=root)


def test_add_parameter_type_refuses_variadic_positional_parameter(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user(*args):\n    return args\n")
    init_git_repo(root)

    with pytest.raises(GitError, match="Variadic positional"):
        add_parameter_type(sample, "load_user", "args", "str", project_root=root)


def test_add_parameter_type_refuses_variadic_keyword_parameter(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user(**kwargs):\n    return kwargs\n")
    init_git_repo(root)

    with pytest.raises(GitError, match="Variadic keyword"):
        add_parameter_type(sample, "load_user", "kwargs", "str", project_root=root)


def test_add_parameter_type_dry_run_does_not_write_and_shows_preview(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user(source):\n    return source\n")
    init_git_repo(root)
    before = sample.read_text(encoding="utf-8")

    exit_code = main(
        [
            "add-parameter-type",
            str(sample),
            "--function",
            "load_user",
            "--parameter",
            "source",
            "--annotation",
            "str",
            "--dry-run",
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Preview diff:" in output
    assert "+def load_user(source: str):" in output
    assert sample.read_text(encoding="utf-8") == before
    assert git_status_short(root) == ""


def test_add_parameter_type_with_test_reports_success(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user(source):\n    return source\n")
    tests_dir = root / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_smoke.py").write_text("from sample import load_user\n\n\ndef test_smoke():\n    assert load_user('x') == 'x'\n", encoding="utf-8")
    init_git_repo(root)
    monkeypatch.setattr(codemods, "run_pytest", lambda cwd, command=None: (0, "ok"))

    result = add_parameter_type(sample, "load_user", "source", "str", project_root=root, run_tests=True)

    assert result.status == "tested"
    assert result.pytest_status == "passed"
    assert result.operation_id is None


def test_add_parameter_type_with_test_failure_propagates_code(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user(source):\n    return source\n")
    init_git_repo(root)
    monkeypatch.setattr(codemods, "run_pytest", lambda cwd, command=None: (7, "boom"))

    result = add_parameter_type(sample, "load_user", "source", "str", project_root=root, run_tests=True)

    assert result.status == "failed"
    assert result.pytest_exit_code == 7
    assert result.exit_code == 3


def test_add_parameter_type_logs_sqlite_record(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user(source):\n    return source\n")
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"

    result = add_parameter_type(sample, "load_user", "source", "str", project_root=root, db_path=db_path)

    row = read_rows(db_path)[0]
    assert row[0] == "add-parameter-type"
    assert row[1] == "applied"
    assert row[2] == "load_user"
    assert row[3] == "source"
    assert result.operation_id is not None
    assert result.logged is True


def test_add_parameter_type_rejects_git_dirty(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user(source):\n    return source\n")
    init_git_repo(root)
    sample.write_text(sample.read_text(encoding="utf-8") + "\n# dirty\n", encoding="utf-8")

    with pytest.raises(GitError, match="Git status is not clean"):
        add_parameter_type(sample, "load_user", "source", "str", project_root=root)


def test_add_parameter_type_cli_json_is_structured(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user(source):\n    return source\n")
    init_git_repo(root)

    exit_code = main(
        [
            "add-parameter-type",
            str(sample),
            "--function",
            "load_user",
            "--parameter",
            "source",
            "--annotation",
            "str | None",
            "--dry-run",
            "--format",
            "json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["protocol_schema_version"] == "1.0"
    assert payload["command"] == "add-parameter-type"
    assert payload["ok"] is True
    assert payload["status"] == "preview"
    assert payload["result"]["operation"] == "add-parameter-type"
    assert payload["result"]["target"]["parameter"] == "source"
    assert payload["result"]["annotation"] == "str | None"
    assert payload["result"]["written"] is False
    assert payload["result"]["logged"] is False
    assert payload["result"]["rollback_available"] is False
    assert payload["result"]["operation_id"] is None


def test_add_parameter_type_cli_text_mentions_parameter(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user(source):\n    return source\n")
    init_git_repo(root)

    exit_code = main(
        [
            "add-parameter-type",
            str(sample),
            "--function",
            "load_user",
            "--parameter",
            "source",
            "--annotation",
            "str",
            "--dry-run",
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Operation:" in output
    assert "add-parameter-type" in output
    assert "Parameter:" in output
    assert "source" in output


def test_add_parameter_type_rollback_restores_crlf_bytes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = root / "sample.py"
    original = b"def load_user(source):\r\n    return source\r\n"
    sample.write_bytes(original)
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"

    add_parameter_type(sample, "load_user", "source", "str", project_root=root, db_path=db_path)
    commit_all(root, "annotate")
    rollback_last(db_path)

    assert sample.read_bytes() == original


def test_add_parameter_type_rollback_by_id_restores_and_blocks_second_rollback(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = root / "sample.py"
    original = b"\xef\xbb\xbfdef load_user(source):\n    return source\n"
    sample.write_bytes(original)
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"

    add_parameter_type(sample, "load_user", "source", "str", project_root=root, db_path=db_path)
    commit_all(root, "annotate")
    operation_id = latest_operation_id(db_path)
    rollback_by_id(db_path, operation_id, current_root=root)
    commit_all(root, "restore")

    with pytest.raises(GitError, match="already been rolled back"):
        rollback_by_id(db_path, operation_id, current_root=root)

    assert sample.read_bytes() == original
