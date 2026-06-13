from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

import surepython.codemods as codemods
from surepython.cli import main
from surepython.codemods import add_docstring, add_import, add_return_type
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
            SELECT operation, status, symbol, import_statement, import_binding, source_operation_id
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


def test_add_import_to_simple_module_inserts_statement(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "VALUE = 1\n")
    init_git_repo(root)

    result = add_import(sample, "import json", project_root=root)

    assert result.status == "applied"
    assert result.binding == "json"
    assert sample.read_text(encoding="utf-8").startswith("import json\n")


def test_add_import_preserves_module_prefix_and_future_imports(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(
        root,
        "#!/usr/bin/env python\n"
        "# -*- coding: utf-8 -*-\n\n"
        "\"\"\"Module documentation.\"\"\"\n\n"
        "from __future__ import annotations\n\n"
        "# keep this comment\n"
        "VALUE = 1\n",
    )
    init_git_repo(root)

    add_import(sample, "from pathlib import Path", project_root=root)
    text = sample.read_text(encoding="utf-8")

    assert text.startswith("#!/usr/bin/env python\n# -*- coding: utf-8 -*-\n\n\"\"\"Module documentation.\"\"\"\n\n")
    assert "from __future__ import annotations\nfrom pathlib import Path\n" in text
    assert "# keep this comment\nVALUE = 1" in text


def test_add_import_supports_alias_binding_and_qualified_module(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "VALUE = 1\n")
    init_git_repo(root)

    result = add_import(sample, "from typing import Any as TypingAny", project_root=root)

    assert result.binding == "TypingAny"
    assert "from typing import Any as TypingAny" in sample.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "statement",
    [
        "",
        "Path",
        "x = 1",
        "import os; import sys",
        "import os, sys",
        "from typing import Any, Iterable",
        "from typing import *",
        "from .models import User",
    ],
)
def test_add_import_refuses_invalid_statements(tmp_path: Path, monkeypatch, statement: str) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "VALUE = 1\n")
    init_git_repo(root)

    with pytest.raises(GitError):
        add_import(sample, statement, project_root=root)


def test_add_import_refuses_duplicate_and_binding_conflict(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "import json\nVALUE = 1\n")
    init_git_repo(root)

    with pytest.raises(GitError, match="already exists"):
        add_import(sample, "import json", project_root=root)

    sample.write_text("import pandas as pd\nVALUE = 1\n", encoding="utf-8")
    commit_all(root, "switch import")

    with pytest.raises(GitError, match="binding already exists"):
        add_import(sample, "import polars as pd", project_root=root)


def test_add_import_json_dry_run_is_structured_and_quiet(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "VALUE = 1\n")
    init_git_repo(root)
    before = sample.read_text(encoding="utf-8")

    exit_code = main(
        [
            "add-import",
            str(sample),
            "--statement",
            "from pathlib import Path",
            "--dry-run",
            "--format",
            "json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["protocol_schema_version"] == "1.0"
    assert payload["command"] == "add-import"
    assert payload["ok"] is True
    assert payload["status"] == "preview"
    assert payload["error"] is None
    assert payload["result"]["statement"] == "from pathlib import Path"
    assert payload["result"]["binding"] == "Path"
    assert payload["result"]["target"]["binding"] == "Path"
    assert payload["result"]["operation_id"] is None
    assert payload["result"]["rollback_available"] is False
    assert payload["result"]["written"] is False
    assert payload["result"]["logged"] is False
    assert sample.read_text(encoding="utf-8") == before
    assert git_status_short(root) == ""


def test_add_import_application_logs_operation_and_supports_rollback_by_id(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "VALUE = 1\n")
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"
    monkeypatch.setattr(codemods, "run_pytest", lambda cwd, command=None: (0, "ok"))

    exit_code = main(
        [
            "add-import",
            str(sample),
            "--statement",
            "from pathlib import Path",
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
    assert payload["result"]["binding"] == "Path"
    assert payload["result"]["operation_id"] is not None
    assert payload["result"]["logged"] is True
    assert payload["result"]["rollback_available"] is True
    assert payload["result"]["tests"]["status"] == "passed"
    assert payload["result"]["tests"]["exit_code"] == 0
    assert "from pathlib import Path" in sample.read_text(encoding="utf-8")
    assert read_rows(db_path)[0][:5] == (
        "add-import",
        "tested",
        "Path",
        "from pathlib import Path",
        "Path",
    )

    commit_all(root, "apply import")
    operation_id = latest_operation_id(db_path)
    result = rollback_by_id(db_path, operation_id, current_root=root)

    assert result.status == "rolled_back"
    assert "from pathlib import Path" not in sample.read_text(encoding="utf-8")
    assert read_rows(db_path)[-1][0] == "rollback"
    assert read_rows(db_path)[-1][5] == operation_id


def test_add_import_with_test_propagates_pytest_failure(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "VALUE = 1\n")
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"
    monkeypatch.setattr(codemods, "run_pytest", lambda cwd, command=None: (1, "boom"))

    exit_code = main(
        [
            "add-import",
            str(sample),
            "--statement",
            "import json",
            "--test",
            "--db",
            str(db_path),
            "--format",
            "json",
        ]
    )

    assert exit_code == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["status"] == "failed"
    assert payload["error"]["code"] == "TESTS_FAILED"
    assert payload["result"]["tests"]["status"] == "failed"
    assert payload["result"]["tests"]["exit_code"] == 1
    assert "import json" in sample.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "content",
    [
        b"VALUE = 1\n",
        b"VALUE = 1\r\n",
        b"\xef\xbb\xbfVALUE = 1\n",
        b"VALUE = 1",
    ],
)
def test_add_import_rollback_restores_exact_bytes(tmp_path: Path, monkeypatch, content: bytes) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_bytes_sample(root, content)
    original = sample.read_bytes()
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"

    add_import(sample, "from pathlib import Path", project_root=root, db_path=db_path)
    commit_all(root, "apply import")

    result = rollback_last(db_path)

    assert result.status == "rolled_back"
    assert sample.read_bytes() == original
    assert git_status_short(root) != ""


def test_add_import_double_rollback_is_refused_after_commit(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "VALUE = 1\n")
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"

    add_import(sample, "from pathlib import Path", project_root=root, db_path=db_path)
    commit_all(root, "apply import")
    operation_id = latest_operation_id(db_path)
    rollback_by_id(db_path, operation_id, current_root=root)
    commit_all(root, "apply rollback")

    with pytest.raises(GitError, match="already been rolled back"):
        rollback_by_id(db_path, operation_id, current_root=root)


def test_add_import_rollback_by_id_selects_the_requested_operation_only(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    file_a = root / "a.py"
    file_b = root / "b.py"
    file_c = root / "c.py"
    file_a.write_text("def alpha():\n    return 1\n", encoding="utf-8")
    file_b.write_text("def beta():\n    return 2\n", encoding="utf-8")
    file_c.write_text("def gamma():\n    return 3\n", encoding="utf-8")
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"

    add_docstring(file_a, "alpha", project_root=root, db_path=db_path)
    commit_all(root, "apply a")
    add_return_type(file_b, "beta", "int", project_root=root, db_path=db_path)
    commit_all(root, "apply b")
    add_docstring(file_c, "gamma", project_root=root, db_path=db_path)
    commit_all(root, "apply c")

    operation_id = latest_operation_id(db_path) - 1
    before_a = file_a.read_text(encoding="utf-8")
    before_c = file_c.read_text(encoding="utf-8")

    result = rollback_by_id(db_path, operation_id, current_root=root)

    assert result.status == "rolled_back"
    assert "-> int" not in file_b.read_text(encoding="utf-8")
    assert file_a.read_text(encoding="utf-8") == before_a
    assert file_c.read_text(encoding="utf-8") == before_c
