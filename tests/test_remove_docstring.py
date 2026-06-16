from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

from surepython.cli import main
from surepython.codemods import remove_docstring
from surepython.git_tools import GitError
from surepython.rollback import rollback_by_id


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
            SELECT operation, status, symbol, target_kind, expected_docstring_text,
                   removed_docstring_text, docstring_replacement_statement, source_operation_id
            FROM surepython_operations
            ORDER BY id
            """
        ).fetchall()


def latest_operation_id(db_path: Path) -> int:
    with sqlite3.connect(str(db_path)) as connection:
        row = connection.execute("SELECT id FROM surepython_operations ORDER BY id DESC LIMIT 1").fetchone()
    assert row is not None
    return int(row[0])


def test_remove_docstring_removes_class_method_and_preserves_other_members(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = root / "sample.py"
    sample.write_text(
        "class Service:\n"
        "    @classmethod\n"
        "    def build(cls):\n"
        "        \"\"\"Build a service.\"\"\"\n"
        "        return cls()\n\n"
        "    def keep(self):\n"
        "        return 'keep'\n",
        encoding="utf-8",
    )
    init_git_repo(root)

    result = remove_docstring(sample, "Service.build", "Build a service.", project_root=root)
    text = sample.read_text(encoding="utf-8")

    assert result.target_kind == "method"
    assert result.removed_docstring_text == "Build a service."
    assert result.docstring_replacement_statement is None
    assert '"""Build a service."""' not in text
    assert "@classmethod" in text
    assert "def keep(self):" in text
    assert git_status_short(root) != ""


def test_remove_docstring_inserts_pass_for_docstring_only_function(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = root / "sample.py"
    sample.write_text(
        "def placeholder():\n"
        "    '''Not implemented yet.'''\n",
        encoding="utf-8",
    )
    init_git_repo(root)

    result = remove_docstring(sample, "placeholder", "Not implemented yet.", project_root=root)

    assert result.target_kind == "function"
    assert result.docstring_replacement_statement == "pass"
    assert sample.read_text(encoding="utf-8") == "def placeholder():\n    pass\n"


def test_remove_docstring_supports_async_function(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = root / "sample.py"
    sample.write_text(
        "async def fetch(url: str) -> str:\n"
        "    \"\"\"Fetch a URL asynchronously.\"\"\"\n"
        "    return url\n",
        encoding="utf-8",
    )
    init_git_repo(root)

    result = remove_docstring(sample, "fetch", "Fetch a URL asynchronously.", project_root=root)

    assert result.target_kind == "function"
    assert "async def fetch(url: str) -> str:" in sample.read_text(encoding="utf-8")
    assert '"""Fetch a URL asynchronously."""' not in sample.read_text(encoding="utf-8")


def test_remove_docstring_supports_module_docstring_and_preserves_header(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = root / "sample.py"
    sample.write_text(
        "#!/usr/bin/env python\n"
        "# -*- coding: utf-8 -*-\n"
        '"""Module documentation."""\n\n'
        "from __future__ import annotations\n\n"
        "import json\n",
        encoding="utf-8",
    )
    init_git_repo(root)

    result = remove_docstring(sample, "module", "Module documentation.", project_root=root)
    text = sample.read_text(encoding="utf-8")

    assert result.target_kind == "module"
    assert '"""Module documentation."""' not in text
    assert text.startswith("#!/usr/bin/env python\n# -*- coding: utf-8 -*-\n\n")
    assert "from __future__ import annotations" in text
    assert "import json" in text


def test_remove_docstring_preserves_comments_and_removes_inline_comment(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = root / "sample.py"
    sample.write_text(
        "def run():\n"
        "    # Public API documentation\n"
        "    \"\"\"Run the operation.\"\"\"  # public documentation\n"
        "    # Actual implementation\n"
        "    return 1\n",
        encoding="utf-8",
    )
    init_git_repo(root)

    result = remove_docstring(sample, "run", "Run the operation.", project_root=root)
    text = sample.read_text(encoding="utf-8")

    assert result.removed_docstring_text == "Run the operation."
    assert "# Public API documentation" in text
    assert "# Actual implementation" in text
    assert "# public documentation" not in text


def test_remove_docstring_refuses_mismatch(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = root / "sample.py"
    sample.write_text(
        "def run():\n"
        "    \"\"\"Run safely.\"\"\"\n"
        "    return 1\n",
        encoding="utf-8",
    )
    init_git_repo(root)

    with pytest.raises(GitError) as excinfo:
        remove_docstring(sample, "run", "Run quickly.", project_root=root)

    assert excinfo.value.code == "DOCSTRING_MISMATCH"
    assert sample.read_text(encoding="utf-8").startswith("def run():")


def test_remove_docstring_refuses_non_docstring_string(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = root / "sample.py"
    sample.write_text(
        "def run():\n"
        "    prepare()\n"
        "    \"\"\"Do not remove this string.\"\"\"\n"
        "    return 1\n",
        encoding="utf-8",
    )
    init_git_repo(root)

    with pytest.raises(GitError) as excinfo:
        remove_docstring(sample, "run", "Do not remove this string.", project_root=root)

    assert excinfo.value.code == "DOCSTRING_NOT_FOUND"
    assert '"""Do not remove this string."""' in sample.read_text(encoding="utf-8")


def test_remove_docstring_refuses_inline_suite_docstring(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = root / "sample.py"
    sample.write_text('def run(): """Run."""\n', encoding="utf-8")
    init_git_repo(root)

    with pytest.raises(GitError) as excinfo:
        remove_docstring(sample, "run", "Run.", project_root=root)

    assert excinfo.value.code == "DOCSTRING_INLINE_SUITE_UNSUPPORTED"


def test_remove_docstring_json_dry_run_is_structured_and_quiet(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = root / "sample.py"
    sample.write_text(
        "def run():\n"
        "    \"\"\"Run.\"\"\"\n"
        "    return 1\n",
        encoding="utf-8",
    )
    init_git_repo(root)
    before = sample.read_text(encoding="utf-8")

    exit_code = main(
        [
            "remove-docstring",
            str(sample),
            "--symbol",
            "run",
            "--expect-docstring",
            "Run.",
            "--dry-run",
            "--format",
            "json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["protocol_schema_version"] == "1.0"
    assert payload["command"] == "remove-docstring"
    assert payload["ok"] is True
    assert payload["status"] == "preview"
    assert payload["result"]["written"] is False
    assert payload["result"]["logged"] is False
    assert payload["result"]["operation_id"] is None
    assert payload["result"]["target"]["kind"] == "function"
    assert payload["result"]["expected_docstring_text"] == "Run."
    assert sample.read_text(encoding="utf-8") == before
    assert git_status_short(root) == ""


def test_remove_docstring_json_application_with_test_and_db_logs_operation_id(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = root / "sample.py"
    sample.write_text(
        "class Service:\n"
        "    @classmethod\n"
        "    def build(cls):\n"
        "        \"\"\"Build a service.\"\"\"\n"
        "        return cls()\n",
        encoding="utf-8",
    )
    init_git_repo(root)
    db_path = root / "surepython_lab.db"
    monkeypatch.setattr("surepython.codemods.run_pytest", lambda cwd, command=None: (0, "ok"))

    exit_code = main(
        [
            "remove-docstring",
            str(sample),
            "--symbol",
            "Service.build",
            "--expect-docstring",
            "Build a service.",
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
    assert payload["result"]["tests"]["status"] == "passed"
    assert payload["result"]["tests"]["exit_code"] == 0
    rows = read_rows(db_path)
    assert len(rows) == 1
    assert rows[0][0] == "remove-docstring"
    assert rows[0][1] == "applied" or rows[0][1] == "tested"
    assert rows[0][2] == "Service.build"


def test_remove_docstring_rollback_restores_bom_crlf_exactly(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    content = (
        b"\xef\xbb\xbfclass SampleClass:\r\n"
        b"    \"\"\"Represent a sample.\"\"\"\r\n"
    )
    sample = root / "sample.py"
    original = content
    sample.write_bytes(content)
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"

    result = remove_docstring(sample, "SampleClass", "Represent a sample.", project_root=root, db_path=db_path)
    commit_all(root, "remove docstring")
    operation_id = result.operation_id
    assert operation_id is not None

    rollback_result = rollback_by_id(db_path, operation_id, current_root=root)
    assert rollback_result.status == "rolled_back"
    assert sample.read_bytes() == original
    commit_all(root, "apply rollback")

    with pytest.raises(GitError, match="already been rolled back"):
        rollback_by_id(db_path, operation_id, current_root=root)

