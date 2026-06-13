from __future__ import annotations

import json
import subprocess
import sqlite3
import hashlib
from pathlib import Path

import pytest

from surepython.cli import main
from surepython.codemods import add_docstring, add_parameter_type
from surepython.datasette_log import OperationRecord, insert_record, now_utc_iso
from surepython.git_tools import GitError
from surepython.rollback import rollback_by_id, rollback_last


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_module.py"


def init_git_repo(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "surepython@example.com"], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "SurePython"], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "baseline"], cwd=str(root), check=True, capture_output=True, text=True)


def commit_all(root: Path, message: str) -> None:
    subprocess.run(["git", "add", "."], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", message], cwd=str(root), check=True, capture_output=True, text=True)


def write_fixture_file(root: Path) -> Path:
    sample = root / "sample.py"
    sample.write_text(FIXTURE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    return sample


def write_bytes_fixture_file(root: Path, content: bytes) -> Path:
    sample = root / "sample.py"
    sample.write_bytes(content)
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


def create_legacy_operations_table(db_path: Path) -> None:
    with sqlite3.connect(str(db_path)) as connection:
        connection.execute(
            """
            CREATE TABLE surepython_operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                project_path TEXT NOT NULL,
                file_path TEXT NOT NULL,
                operation TEXT NOT NULL,
                symbol TEXT,
                before_sha256 TEXT,
                after_sha256 TEXT,
                git_diff TEXT,
                pytest_command TEXT,
                pytest_exit_code INTEGER,
                pytest_status TEXT,
                status TEXT NOT NULL,
                message TEXT
            )
            """
        )
        connection.commit()


def insert_legacy_operation(
    db_path: Path,
    *,
    created_at: str,
    project_path: str,
    file_path: str,
    operation: str,
    symbol: str,
    before_sha256: str,
    after_sha256: str,
    git_diff: str,
    status: str,
    message: str,
) -> int:
    with sqlite3.connect(str(db_path)) as connection:
        cursor = connection.execute(
            """
            INSERT INTO surepython_operations (
                created_at,
                project_path,
                file_path,
                operation,
                symbol,
                before_sha256,
                after_sha256,
                git_diff,
                pytest_command,
                pytest_exit_code,
                pytest_status,
                status,
                message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_at,
                project_path,
                file_path,
                operation,
                symbol,
                before_sha256,
                after_sha256,
                git_diff,
                None,
                None,
                None,
                status,
                message,
            ),
        )
        connection.commit()
        return int(cursor.lastrowid)


def read_operations(db_path: Path) -> list[tuple[str, str, str | None]]:
    with sqlite3.connect(str(db_path)) as connection:
        return connection.execute(
            """
            SELECT operation, status, symbol
            FROM surepython_operations
            ORDER BY id
            """
        ).fetchall()


def latest_operation_id(db_path: Path) -> int:
    with sqlite3.connect(str(db_path)) as connection:
        row = connection.execute("SELECT id FROM surepython_operations ORDER BY id DESC LIMIT 1").fetchone()
    assert row is not None
    return int(row[0])


def prepare_logged_add_docstring(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "project"
    root.mkdir()
    sample = write_fixture_file(root)
    init_git_repo(root)
    db_path = tmp_path / "surepython_lab.db"

    add_docstring(sample, "SampleClass.sample_method", project_root=root, db_path=db_path)
    commit_all(root, "apply docstring")

    return root, sample, db_path


def prepare_logged_add_docstring_bytes(
    tmp_path: Path, content: bytes
) -> tuple[Path, Path, Path, bytes]:
    root = tmp_path / "project"
    root.mkdir()
    sample = write_bytes_fixture_file(root, content)
    original = sample.read_bytes()
    init_git_repo(root)
    db_path = tmp_path / "surepython_lab.db"

    add_docstring(sample, "SampleClass.sample_method", project_root=root, db_path=db_path)
    commit_all(root, "apply docstring")

    return root, sample, db_path, original


def prepare_logged_add_parameter_type(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "project"
    root.mkdir()
    sample = root / "sample.py"
    sample.write_text("def load_user(source):\n    return source\n", encoding="utf-8")
    init_git_repo(root)
    db_path = tmp_path / "surepython_lab.db"

    add_parameter_type(sample, "load_user", "source", "str", project_root=root, db_path=db_path)
    commit_all(root, "apply parameter annotation")

    return root, sample, db_path


def test_rollback_last_dry_run_shows_diff_without_writing(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root, sample, db_path = prepare_logged_add_docstring(tmp_path)
    before = sample.read_text(encoding="utf-8")

    exit_code = main(["rollback", "--last", "--db", str(db_path), "--dry-run"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Dry run; no files changed." in output
    assert "Rollback diff:" in output
    assert '-        """TODO: Document this function."""' in output
    assert sample.read_text(encoding="utf-8") == before
    assert git_status_short(root) == ""


def test_rollback_last_applies_single_logged_add_docstring(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root, sample, db_path = prepare_logged_add_docstring(tmp_path)

    result = rollback_last(db_path)
    updated = sample.read_text(encoding="utf-8")

    assert result.status == "rolled_back"
    assert '"""TODO: Document this function."""' not in updated
    assert git_status_short(root) != ""
    assert read_operations(db_path) == [
        ("add-docstring", "applied", "SampleClass.sample_method"),
        ("rollback", "rolled_back", "SampleClass.sample_method"),
    ]


def test_rollback_restores_lf_bytes_exactly(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    content = (
        b"class SampleClass:\n"
        b"    def sample_method(self):\n"
        b"        return 'class'\n"
    )
    _, sample, db_path, original = prepare_logged_add_docstring_bytes(tmp_path, content)

    result = rollback_last(db_path)

    assert result.status == "rolled_back"
    assert sample.read_bytes() == original


def test_rollback_restores_crlf_bytes_exactly(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    content = (
        b"class SampleClass:\r\n"
        b"    def sample_method(self):\r\n"
        b"        return 'class'\r\n"
    )
    _, sample, db_path, original = prepare_logged_add_docstring_bytes(tmp_path, content)

    result = rollback_last(db_path)

    assert result.status == "rolled_back"
    assert sample.read_bytes() == original


def test_rollback_preserves_final_newline(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    content = (
        b"class SampleClass:\n"
        b"    def sample_method(self):\n"
        b"        return 'class'\n"
    )
    _, sample, db_path, original = prepare_logged_add_docstring_bytes(tmp_path, content)

    rollback_last(db_path)

    assert sample.read_bytes().endswith(b"\n")
    assert sample.read_bytes() == original


def test_rollback_cli_requires_db(capsys) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["rollback", "--last", "--dry-run"])

    assert excinfo.value.code == 2
    assert "--db" in capsys.readouterr().err


def test_rollback_cli_requires_exactly_one_selector(capsys) -> None:
    exit_code = main(["rollback", "--db", "x.db"])

    assert exit_code == 2
    assert "rollback requires --last or --id" in capsys.readouterr().err.lower()


def test_rollback_cli_rejects_selector_conflict(capsys) -> None:
    exit_code = main(["rollback", "--last", "--id", "1", "--db", "x.db"])

    assert exit_code == 2
    assert "either --last or --id, not both" in capsys.readouterr().err.lower()


def test_rollback_refuses_dirty_git_status(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root, sample, db_path = prepare_logged_add_docstring(tmp_path)
    sample.write_text(sample.read_text(encoding="utf-8") + "\n# dirty\n", encoding="utf-8")

    try:
        rollback_last(db_path, dry_run=True)
    except GitError as exc:
        assert "git status" in str(exc).lower()
    else:
        raise AssertionError("Expected dirty repo refusal")

    assert git_status_short(root) != ""


def test_rollback_refuses_hash_mismatch(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root, sample, db_path = prepare_logged_add_docstring(tmp_path)
    sample.write_text(sample.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
    commit_all(root, "change after logged operation")

    try:
        rollback_last(db_path, dry_run=True)
    except GitError as exc:
        assert "after_sha256" in str(exc)
    else:
        raise AssertionError("Expected hash mismatch refusal")


def test_rollback_refuses_when_restored_bytes_do_not_match_before_sha(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root, sample, db_path = prepare_logged_add_docstring(tmp_path)
    before_refusal = sample.read_bytes()
    with sqlite3.connect(str(db_path)) as connection:
        connection.execute(
            "UPDATE surepython_operations SET before_sha256 = ? WHERE operation = ?",
            ("0" * 64, "add-docstring"),
        )
        connection.commit()

    try:
        rollback_last(db_path)
    except GitError as exc:
        assert "before_sha256" in str(exc)
    else:
        raise AssertionError("Expected restored hash refusal")

    assert sample.read_bytes() == before_refusal
    assert git_status_short(root) == ""


def test_rollback_by_id_dry_run_shows_diff_without_writing(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root, sample, db_path = prepare_logged_add_docstring(tmp_path)
    operation_id = latest_operation_id(db_path)
    before = sample.read_text(encoding="utf-8")
    monkeypatch.chdir(root)

    exit_code = main(["rollback", "--id", str(operation_id), "--db", str(db_path), "--dry-run", "--format", "json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["status"] == "preview"
    assert payload["result"]["selector"] == {"type": "operation_id", "value": operation_id}
    assert payload["result"]["source_operation_id"] == operation_id
    assert payload["result"]["bytes_equal"] is True
    assert sample.read_text(encoding="utf-8") == before
    assert git_status_short(root) == ""


def test_rollback_by_id_applies_and_logs_source_operation_id(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root, sample, db_path = prepare_logged_add_docstring(tmp_path)
    operation_id = latest_operation_id(db_path)
    monkeypatch.chdir(root)

    result = rollback_by_id(db_path, operation_id, current_root=root)

    assert result.status == "rolled_back"
    assert result.selector_type == "operation_id"
    assert result.selector_value == operation_id
    assert result.source_operation_id == operation_id
    assert result.bytes_equal is True
    assert result.byte_exact is True
    assert '"""TODO: Document this function."""' not in sample.read_text(encoding="utf-8")
    assert read_operations(db_path) == [
        ("add-docstring", "applied", "SampleClass.sample_method"),
        ("rollback", "rolled_back", "SampleClass.sample_method"),
    ]


def test_rollback_last_restores_parameter_annotation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root, sample, db_path = prepare_logged_add_parameter_type(tmp_path)

    result = rollback_last(db_path)

    assert result.status == "rolled_back"
    assert result.source_operation == "add-parameter-type"
    assert result.parameter == "source"
    assert "source: str" not in sample.read_text(encoding="utf-8")
    assert git_status_short(root) != ""


def test_rollback_by_id_restores_parameter_annotation_and_blocks_second_rollback(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root, sample, db_path = prepare_logged_add_parameter_type(tmp_path)
    operation_id = latest_operation_id(db_path)

    result = rollback_by_id(db_path, operation_id, current_root=root)
    assert result.status == "rolled_back"
    assert result.parameter == "source"
    commit_all(root, "restore parameter annotation")

    with pytest.raises(GitError, match="already been rolled back"):
        rollback_by_id(db_path, operation_id, current_root=root)

    assert "source: str" not in sample.read_text(encoding="utf-8")


def test_rollback_by_id_refuses_invalid_ids(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root, _, db_path = prepare_logged_add_docstring(tmp_path)
    monkeypatch.chdir(root)

    with pytest.raises(GitError, match="positive"):
        rollback_by_id(db_path, 0, current_root=root)
    with pytest.raises(GitError, match="positive"):
        rollback_by_id(db_path, -1, current_root=root)
    with pytest.raises(GitError, match="Operation not found"):
        rollback_by_id(db_path, 999, current_root=root)


def test_rollback_by_id_refuses_project_mismatch(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root, _, db_path = prepare_logged_add_docstring(tmp_path)
    other_root = tmp_path / "other"
    other_root.mkdir()
    init_git_repo(other_root)
    operation_id = latest_operation_id(db_path)

    with pytest.raises(GitError, match="different project"):
        rollback_by_id(db_path, operation_id, current_root=other_root)


def test_rollback_by_id_refuses_unknown_operation_type(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_fixture_file(root)
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"

    current_sha = hashlib.sha256(sample.read_bytes()).hexdigest()
    insert_record(
        db_path,
        OperationRecord(
            created_at=now_utc_iso(),
            project_path=str(root),
            file_path=str(sample),
            operation="unknown-operation",
            symbol="SampleClass.sample_method",
            before_sha256=current_sha,
            after_sha256=current_sha,
            git_diff="",
            pytest_command=None,
            pytest_exit_code=None,
            pytest_status=None,
            status="applied",
            message="unknown",
        ),
    )

    with pytest.raises(GitError, match="not rollback-compatible"):
        rollback_by_id(db_path, 1, current_root=root)


def test_rollback_by_id_refuses_double_rollback(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root, _, db_path = prepare_logged_add_docstring(tmp_path)
    operation_id = latest_operation_id(db_path)

    rollback_by_id(db_path, operation_id, current_root=root)
    commit_all(root, "apply rollback")

    with pytest.raises(GitError, match="already been rolled back"):
        rollback_by_id(db_path, operation_id, current_root=root)


def test_rollback_by_id_refuses_rollback_record_as_source(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root, _, db_path = prepare_logged_add_docstring(tmp_path)
    operation_id = latest_operation_id(db_path)

    rollback_result = rollback_by_id(db_path, operation_id, current_root=root)
    rollback_id = rollback_result.rollback_operation_id
    assert rollback_id is not None
    commit_all(root, "apply rollback")

    with pytest.raises(GitError, match="cannot be rolled back again"):
        rollback_by_id(db_path, rollback_id, current_root=root)


def test_rollback_last_works_with_legacy_schema_without_source_operation_id(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_fixture_file(root)
    init_git_repo(root)
    db_path = tmp_path / "legacy.db"
    original = sample.read_text(encoding="utf-8")
    before_sha = hashlib.sha256(sample.read_bytes()).hexdigest()

    add_docstring(sample, "SampleClass.sample_method", project_root=root)
    after_sha = hashlib.sha256(sample.read_bytes()).hexdigest()
    create_legacy_operations_table(db_path)
    operation_id = insert_legacy_operation(
        db_path,
        created_at=now_utc_iso(),
        project_path=str(root),
        file_path=str(sample),
        operation="add-docstring",
        symbol="SampleClass.sample_method",
        before_sha256=before_sha,
        after_sha256=after_sha,
        git_diff="legacy diff",
        status="applied",
        message="legacy record",
    )
    commit_all(root, "apply legacy docstring")

    result = rollback_last(db_path)

    assert result.source_operation_id == operation_id
    assert sample.read_text(encoding="utf-8") == original


def test_windows_smoke_add_docstring_commit_then_real_rollback(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    content = (
        b"class SampleClass:\r\n"
        b"    def sample_method(self):\r\n"
        b"        return 'class'\r\n"
    )
    root, sample, db_path, original = prepare_logged_add_docstring_bytes(tmp_path, content)

    rollback_last(db_path)


def test_rollback_refuses_unknown_operation_type(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_fixture_file(root)
    init_git_repo(root)
    db_path = tmp_path / "surepython_lab.db"

    before = sample.read_text(encoding="utf-8")
    current_sha = hashlib.sha256(sample.read_bytes()).hexdigest()
    insert_record(
        db_path,
        OperationRecord(
            created_at=now_utc_iso(),
            project_path=str(root),
            file_path=str(sample),
            operation="unknown-operation",
            symbol="SampleClass.sample_method",
            before_sha256=current_sha,
            after_sha256=current_sha,
            git_diff="",
            pytest_command=None,
            pytest_exit_code=None,
            pytest_status=None,
            status="applied",
            message="unknown",
        ),
    )

    with pytest.raises(GitError, match="not rollback-compatible"):
        rollback_last(db_path)
    assert sample.read_text(encoding="utf-8") == before
    assert git_status_short(root) == ""


def test_rollback_json_refuses_unknown_operation_type(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_fixture_file(root)
    init_git_repo(root)
    db_path = tmp_path / "surepython_lab.db"

    before = sample.read_text(encoding="utf-8")
    current_sha = hashlib.sha256(sample.read_bytes()).hexdigest()
    insert_record(
        db_path,
        OperationRecord(
            created_at=now_utc_iso(),
            project_path=str(root),
            file_path=str(sample),
            operation="unknown-operation",
            symbol="SampleClass.sample_method",
            before_sha256=current_sha,
            after_sha256=current_sha,
            git_diff="",
            pytest_command=None,
            pytest_exit_code=None,
            pytest_status=None,
            status="applied",
            message="unknown",
        ),
    )

    exit_code = main(["rollback", "--last", "--db", str(db_path), "--dry-run", "--format", "json"])

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["status"] == "refused"
    assert payload["error"]["code"] == "UNKNOWN_SQLITE_OPERATION"
    assert payload["result"] is None
    assert sample.read_text(encoding="utf-8") == before
    assert git_status_short(root) == ""
