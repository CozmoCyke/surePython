from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

from surepython.cli import main
from surepython.codemods import add_docstring, add_parameter_type, add_return_type
from surepython.protocol import build_protocol_response, dump_json


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
            SELECT operation, status, symbol, before_sha256, after_sha256, pytest_status, source_operation_id
            FROM surepython_operations
            ORDER BY id
            """
        ).fetchall()


def last_operation_id(db_path: Path) -> int:
    with sqlite3.connect(str(db_path)) as connection:
        row = connection.execute(
            "SELECT id FROM surepython_operations ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert row is not None
    return int(row[0])


def test_protocol_envelope_serialization_is_deterministic() -> None:
    payload = build_protocol_response(
        command="add-docstring",
        ok=True,
        status="preview",
        error=None,
        result={"written": False},
        meta={"dry_run": True},
    )
    text = dump_json(payload)

    assert list(json.loads(text)) == [
        "protocol_schema_version",
        "command",
        "ok",
        "status",
        "error",
        "result",
        "meta",
    ]
    assert '"command": "add-docstring"' in text


def test_add_docstring_json_dry_run_is_structured_and_quiet(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = root / "sample.py"
    sample.write_text("class SampleClass:\n    def sample_method(self):\n        return 1\n", encoding="utf-8")
    init_git_repo(root)
    before = sample.read_text(encoding="utf-8")

    exit_code = main(
        [
            "add-docstring",
            str(sample),
            "--function",
            "SampleClass.sample_method",
            "--dry-run",
            "--format",
            "json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["protocol_schema_version"] == "1.0"
    assert payload["command"] == "add-docstring"
    assert payload["ok"] is True
    assert payload["status"] == "preview"
    assert payload["error"] is None
    assert payload["result"]["written"] is False
    assert payload["result"]["logged"] is False
    assert payload["result"]["rollback_available"] is False
    assert payload["result"]["operation_id"] is None
    assert payload["result"]["tests"] is None
    assert payload["result"]["target"]["symbol"] == "SampleClass.sample_method"
    assert sample.read_text(encoding="utf-8") == before
    assert git_status_short(root) == ""


def test_add_return_type_json_dry_run_is_structured_and_quiet(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = root / "sample.py"
    sample.write_text("def load_user():\n    return None\n", encoding="utf-8")
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
            "--format",
            "json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["protocol_schema_version"] == "1.0"
    assert payload["command"] == "add-return-type"
    assert payload["ok"] is True
    assert payload["status"] == "preview"
    assert payload["result"]["annotation"] == "str"
    assert payload["result"]["written"] is False
    assert payload["result"]["logged"] is False
    assert payload["result"]["rollback_available"] is False
    assert payload["result"]["operation_id"] is None
    assert sample.read_text(encoding="utf-8") == before
    assert git_status_short(root) == ""


def test_add_parameter_type_json_dry_run_is_structured_and_quiet(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = root / "sample.py"
    sample.write_text("def load_user(source):\n    return source\n", encoding="utf-8")
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
    assert payload["result"]["annotation"] == "str"
    assert payload["result"]["target"]["parameter"] == "source"
    assert payload["result"]["written"] is False
    assert payload["result"]["logged"] is False
    assert payload["result"]["rollback_available"] is False
    assert payload["result"]["operation_id"] is None
    assert sample.read_text(encoding="utf-8") == before
    assert git_status_short(root) == ""


def test_rollback_json_dry_run_is_structured_and_byte_exact(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = root / "sample.py"
    sample.write_text("class SampleClass:\n    def sample_method(self):\n        return 1\n", encoding="utf-8")
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"
    original = sample.read_bytes()

    add_docstring(sample, "SampleClass.sample_method", project_root=root, db_path=db_path)
    commit_all(root, "apply docstring")
    after_commit = sample.read_bytes()
    operation_id = last_operation_id(db_path)
    monkeypatch.chdir(root)

    exit_code = main(["rollback", "--id", str(operation_id), "--db", str(db_path), "--dry-run", "--format", "json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "rollback"
    assert payload["ok"] is True
    assert payload["status"] == "preview"
    assert payload["result"]["source_operation"] == "add-docstring"
    assert payload["result"]["selector"] == {"type": "operation_id", "value": operation_id}
    assert payload["result"]["source_operation_id"] == operation_id
    assert payload["result"]["operation_id"] is None
    assert payload["result"]["rollback_operation_id"] is None
    assert payload["result"]["written"] is False
    assert payload["result"]["logged"] is False
    assert payload["result"]["bytes_equal"] is True
    assert payload["result"]["byte_exact"] is True
    assert sample.read_bytes() == after_commit
    assert git_status_short(root) == ""

    exit_code = main(["rollback", "--id", str(operation_id), "--db", str(db_path), "--format", "json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["status"] == "rolled_back"
    assert payload["result"]["operation_id"] is not None
    assert payload["result"]["rollback_operation_id"] == payload["result"]["operation_id"]
    assert payload["result"]["logged"] is True
    assert payload["result"]["bytes_equal"] is True
    assert sample.read_bytes() == original
    rows = read_rows(db_path)
    assert rows[-2][0] == "add-docstring"
    assert rows[-1][0] == "rollback"
    assert rows[-1][6] == operation_id


def test_add_return_type_json_application_includes_operation_id_and_tests(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = root / "sample.py"
    sample.write_text("def load_user():\n    return None\n", encoding="utf-8")
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
    assert sample.read_text(encoding="utf-8").startswith("def load_user() -> str | None:")
    assert git_status_short(root) != ""
    assert read_rows(db_path)[0][0] == "add-return-type"


def test_add_parameter_type_json_application_includes_operation_id_and_tests(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = root / "sample.py"
    sample.write_text("def load_user(source):\n    return source\n", encoding="utf-8")
    tests_dir = root / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_smoke.py").write_text(
        "from sample import load_user\n\n"
        "def test_smoke():\n"
        "    assert load_user('x') == 'x'\n",
        encoding="utf-8",
    )
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"

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
    assert "def load_user(source: str):" in sample.read_text(encoding="utf-8")
    assert git_status_short(root) != ""
    assert read_rows(db_path)[0][0] == "add-parameter-type"


def test_rollback_json_refuses_missing_selector(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    init_git_repo(root)

    exit_code = main(["rollback", "--db", str(tmp_path / "surepython.db"), "--format", "json"])

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["status"] == "refused"
    assert payload["error"]["code"] == "OPERATION_ID_REQUIRED"
    assert payload["result"] is None


def test_rollback_json_refuses_selector_conflict(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    init_git_repo(root)

    exit_code = main(["rollback", "--last", "--id", "1", "--db", str(tmp_path / "surepython.db"), "--format", "json"])

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["status"] == "refused"
    assert payload["error"]["code"] == "ROLLBACK_SELECTOR_CONFLICT"
    assert payload["result"] is None
