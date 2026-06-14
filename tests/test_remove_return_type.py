from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

import surepython.codemods as codemods
from surepython.cli import main
from surepython.codemods import remove_return_type
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
            SELECT operation, status, symbol, expected_return_annotation, return_annotation, pytest_status, source_operation_id
            FROM surepython_operations
            ORDER BY id
            """
        ).fetchall()


def last_operation_id(db_path: Path) -> int:
    with sqlite3.connect(str(db_path)) as connection:
        row = connection.execute("SELECT id FROM surepython_operations ORDER BY id DESC LIMIT 1").fetchone()
    assert row is not None
    return int(row[0])


def write_sample(root: Path, content: bytes | str) -> Path:
    sample = root / "sample.py"
    if isinstance(content, bytes):
        sample.write_bytes(content)
    else:
        sample.write_text(content, encoding="utf-8")
    return sample


def test_remove_return_type_to_qualified_method_only(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(
        root,
        "def load_user() -> str:\n"
        "    return 'global'\n\n"
        "class UserService:\n"
        "    def load_user(self) -> str:\n"
        "        return 'class'\n\n"
        "class OtherService:\n"
        "    def load_user(self) -> str:\n"
        "        return 'other'\n",
    )
    init_git_repo(root)

    result = remove_return_type(sample, "UserService.load_user", "str", project_root=root)
    updated = sample.read_text(encoding="utf-8")

    assert result.status == "applied"
    assert result.annotation == "str"
    assert "def load_user() -> str:" in updated
    assert "class UserService:\n    def load_user(self):" in updated
    assert "class OtherService:\n    def load_user(self) -> str:" in updated


def test_remove_return_type_supports_async_function(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "async def fetch() -> User | None:\n    return None\n")
    init_git_repo(root)

    result = remove_return_type(sample, "fetch", "User | None", project_root=root)

    assert result.status == "applied"
    assert "async def fetch():" in sample.read_text(encoding="utf-8")


def test_remove_return_type_preserves_multiline_signature_and_comment(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(
        root,
        "def render(\n"
        "    source: str,\n"
        "    /,\n"
        "    prefix: str = 'x',\n"
        "    *,\n"
        "    suffix: str = 'y',  # keep comment\n"
        ") -> str:\n"
        "    return source\n",
    )
    init_git_repo(root)

    remove_return_type(sample, "render", "str", project_root=root)
    updated = sample.read_text(encoding="utf-8")

    assert "def render(" in updated
    assert "prefix: str = 'x'," in updated
    assert "suffix: str = 'y',  # keep comment" in updated
    assert ") -> str:" not in updated
    assert "):" in updated


def test_remove_return_type_preserves_classmethod_decorator(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(
        root,
        "class UserService:\n"
        "    @classmethod\n"
        "    def load_user(cls) -> str:\n"
        "        return cls()\n",
    )
    init_git_repo(root)

    remove_return_type(sample, "UserService.load_user", "str", project_root=root)
    updated = sample.read_text(encoding="utf-8")

    assert "@classmethod" in updated
    assert "def load_user(cls):" in updated


def test_remove_return_type_dry_run_json_is_preview_and_quiet(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user() -> str:\n    return None\n")
    init_git_repo(root)
    before = sample.read_bytes()

    exit_code = main(
        [
            "remove-return-type",
            str(sample),
            "--function",
            "load_user",
            "--expect-annotation",
            "str",
            "--dry-run",
            "--format",
            "json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["protocol_schema_version"] == "1.0"
    assert payload["command"] == "remove-return-type"
    assert payload["ok"] is True
    assert payload["status"] == "preview"
    assert payload["result"]["expected_annotation"] == "str"
    assert payload["result"]["annotation"] == "str"
    assert payload["result"]["written"] is False
    assert payload["result"]["logged"] is False
    assert payload["result"]["rollback_available"] is False
    assert payload["result"]["operation_id"] is None
    assert sample.read_bytes() == before
    assert git_status_short(root) == ""


def test_remove_return_type_json_application_includes_operation_id_and_tests(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user() -> str:\n    return None\n")
    tests_dir = root / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_smoke.py").write_text(
        "from sample import load_user\n\n"
        "def test_smoke():\n"
        "    assert load_user() is None\n",
        encoding="utf-8",
    )
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"
    monkeypatch.setattr(codemods, "run_pytest", lambda cwd, command=None: (0, "ok"))

    exit_code = main(
        [
            "remove-return-type",
            str(sample),
            "--function",
            "load_user",
            "--expect-annotation",
            "str",
            "--test",
            "--db",
            str(db_path),
            "--format",
            "json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["status"] == "tested"
    assert payload["result"]["operation_id"] is not None
    assert payload["result"]["logged"] is True
    assert payload["result"]["rollback_available"] is True
    assert payload["result"]["tests"]["status"] == "passed"
    assert payload["result"]["tests"]["exit_code"] == 0
    assert "def load_user():" in sample.read_text(encoding="utf-8")
    row = read_rows(db_path)[0]
    assert row[0] == "remove-return-type"
    assert row[1] == "tested"
    assert row[3] == "str"
    assert row[4] == "str"


def test_remove_return_type_refuses_annotation_mismatch_json(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user() -> str:\n    return None\n")
    init_git_repo(root)
    before = sample.read_text(encoding="utf-8")

    exit_code = main(
        [
            "remove-return-type",
            str(sample),
            "--function",
            "load_user",
            "--expect-annotation",
            "int",
            "--format",
            "json",
        ]
    )

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["status"] == "refused"
    assert payload["error"]["code"] == "RETURN_ANNOTATION_MISMATCH"
    assert payload["result"] is None
    assert sample.read_text(encoding="utf-8") == before
    assert git_status_short(root) == ""


def test_remove_return_type_refuses_missing_annotation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user():\n    return None\n")
    init_git_repo(root)

    with pytest.raises(GitError, match="return annotation"):
        remove_return_type(sample, "load_user", "str", project_root=root)


@pytest.mark.parametrize(
    "expected",
    ["", "list["],
)
def test_remove_return_type_refuses_invalid_expected_annotation(
    tmp_path: Path, monkeypatch, expected: str
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user() -> str:\n    return None\n")
    init_git_repo(root)

    with pytest.raises(GitError) as excinfo:
        remove_return_type(sample, "load_user", expected, project_root=root)

    assert excinfo.value.code in {"RETURN_ANNOTATION_REQUIRED", "RETURN_ANNOTATION_INVALID"}


@pytest.mark.parametrize(
    "content, expected",
    [
        (b"def load_user() -> str:\n    return None\n", b"def load_user() -> str:\n    return None\n"),
        (b"def load_user() -> str:\r\n    return None\r\n", b"def load_user() -> str:\r\n    return None\r\n"),
        (b"\xef\xbb\xbfdef load_user() -> str:\r\n    return None\r\n", b"\xef\xbb\xbfdef load_user() -> str:\r\n    return None\r\n"),
    ],
)
def test_remove_return_type_rollback_by_id_restores_bytes_exactly(
    tmp_path: Path, monkeypatch, content: bytes, expected: bytes
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, content)
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"

    remove_return_type(sample, "load_user", "str", project_root=root, db_path=db_path)
    commit_all(root, "remove return annotation")
    operation_id = last_operation_id(db_path)

    result = rollback_by_id(db_path, operation_id, current_root=root)

    assert result.status == "rolled_back"
    assert result.return_annotation == "str"
    assert sample.read_bytes() == expected
    assert read_rows(db_path)[-1][0] == "rollback"
    assert read_rows(db_path)[-1][6] == operation_id


def test_remove_return_type_rollback_last_restores_annotation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user() -> str:\n    return None\n")
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"
    original = sample.read_bytes()

    remove_return_type(sample, "load_user", "str", project_root=root, db_path=db_path)
    commit_all(root, "remove return annotation")

    result = rollback_last(db_path)

    assert result.status == "rolled_back"
    assert sample.read_bytes() == original


def test_remove_return_type_double_rollback_refused(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def load_user() -> str:\n    return None\n")
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"

    remove_return_type(sample, "load_user", "str", project_root=root, db_path=db_path)
    commit_all(root, "remove return annotation")
    operation_id = last_operation_id(db_path)

    rollback_by_id(db_path, operation_id, current_root=root)
    commit_all(root, "restore return annotation")

    with pytest.raises(GitError, match="already been rolled back"):
        rollback_by_id(db_path, operation_id, current_root=root)
