from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

import surepython.codemods as codemods
from surepython.cli import main
from surepython.codemods import remove_import
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
            SELECT operation, status, symbol, expected_import_statement, removed_import_statement,
                   removed_import_binding, import_match_count, source_operation_id
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


@pytest.mark.parametrize(
    "statement, expected_binding, expected_text",
    [
        ("import json", "json", "VALUE = 1\n"),
        ("import numpy as np", "np", "VALUE = 1\n"),
        ("from pathlib import Path", "Path", "VALUE = 1\n"),
        ("from typing import Any as TypingAny", "TypingAny", "VALUE = 1\n"),
    ],
)
def test_remove_import_supports_exact_module_level_statements(
    tmp_path: Path, monkeypatch, statement: str, expected_binding: str, expected_text: str
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, f"{statement}\nVALUE = 1\n")
    init_git_repo(root)

    result = remove_import(sample, statement, project_root=root)

    assert result.status == "applied"
    assert result.target_kind == "module_import"
    assert result.expected_import_statement == statement
    assert result.import_binding == expected_binding
    assert result.import_match_count == 1
    assert sample.read_text(encoding="utf-8") == expected_text
    assert git_status_short(root) != ""


@pytest.mark.parametrize(
    "statement",
    [
        "",
        "json",
        "import os; import sys",
        "import os, sys",
        "from typing import Any, Iterable",
        "from typing import *",
        "from .module import Value",
        "import",
        "from pathlib",
    ],
)
def test_remove_import_refuses_invalid_expected_statements(
    tmp_path: Path, monkeypatch, statement: str
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "import json\nVALUE = 1\n")
    init_git_repo(root)

    with pytest.raises(GitError):
        remove_import(sample, statement, project_root=root)


def test_remove_import_refuses_absent_ambiguous_and_scope_unsupported(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "import os\nVALUE = 1\n")
    init_git_repo(root)

    with pytest.raises(GitError, match="not found"):
        remove_import(sample, "import json", project_root=root)

    sample.write_text("import json\nimport json\nVALUE = 1\n", encoding="utf-8")
    commit_all(root, "duplicate import")
    with pytest.raises(GitError, match="more than once"):
        remove_import(sample, "import json", project_root=root)

    for content in [
        "def helper():\n    import json\n    return json\n",
        "class Box:\n    import json\n",
        "if True:\n    import json\n",
        "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    import json\n",
    ]:
        sample.write_text(content, encoding="utf-8")
        commit_all(root, "nested import")
        with pytest.raises(GitError, match="outside module level"):
            remove_import(sample, "import json", project_root=root)


def test_remove_import_preserves_shebang_encoding_docstring_future_and_comments(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(
        root,
        "#!/usr/bin/env python\n"
        "# -*- coding: utf-8 -*-\n"
        "\"\"\"Module documentation.\"\"\"\n\n"
        "from __future__ import annotations\n\n"
        "# keep this comment\n"
        "import json  # JSON parser\n"
        "from pathlib import Path\n"
        "VALUE = 1\n",
    )
    init_git_repo(root)

    remove_import(sample, "import json", project_root=root)
    text = sample.read_text(encoding="utf-8")

    assert text.startswith(
        "#!/usr/bin/env python\n# -*- coding: utf-8 -*-\n\"\"\"Module documentation.\"\"\"\n\n"
    )
    assert "from __future__ import annotations\n\n" in text
    assert "# keep this comment\n" in text
    assert "from pathlib import Path\n" in text
    assert "import json" not in text


def test_remove_import_json_dry_run_is_structured_and_quiet(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "import json\nVALUE = 1\n")
    init_git_repo(root)
    before = sample.read_text(encoding="utf-8")

    exit_code = main(
        [
            "remove-import",
            str(sample),
            "--expect-statement",
            "import json",
            "--dry-run",
            "--format",
            "json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["protocol_schema_version"] == "1.0"
    assert payload["command"] == "remove-import"
    assert payload["ok"] is True
    assert payload["status"] == "preview"
    assert payload["error"] is None
    assert payload["result"]["operation"] == "remove-import"
    assert payload["result"]["target"]["kind"] == "module_import"
    assert payload["result"]["expected_import_statement"] == "import json"
    assert payload["result"]["removed_import_statement"].startswith("import json")
    assert payload["result"]["binding"] == "json"
    assert payload["result"]["match_count"] == 1
    assert payload["result"]["written"] is False
    assert payload["result"]["logged"] is False
    assert payload["result"]["rollback_available"] is False
    assert payload["result"]["operation_id"] is None
    assert sample.read_text(encoding="utf-8") == before
    assert git_status_short(root) == ""


def test_remove_import_json_application_logs_operation_and_supports_tests(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "import json\nVALUE = 1\n")
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"
    monkeypatch.setattr(codemods, "run_pytest", lambda cwd, command=None: (0, "ok"))

    exit_code = main(
        [
            "remove-import",
            str(sample),
            "--expect-statement",
            "import json",
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
    assert sample.read_text(encoding="utf-8") == "VALUE = 1\n"
    assert read_rows(db_path)[0][0] == "remove-import"


def test_remove_import_json_application_propagates_test_failure(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "import json\nVALUE = 1\n")
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"
    monkeypatch.setattr(codemods, "run_pytest", lambda cwd, command=None: (1, "failed"))

    exit_code = main(
        [
            "remove-import",
            str(sample),
            "--expect-statement",
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
    assert sample.read_text(encoding="utf-8") == "VALUE = 1\n"
    assert read_rows(db_path)[0][0] == "remove-import"


@pytest.mark.parametrize(
    "content, expected_code",
    [
        ("import os\nVALUE = 1\n", "IMPORT_NOT_FOUND"),
        ("import json\nimport json\nVALUE = 1\n", "IMPORT_AMBIGUOUS"),
        ("def helper():\n    import json\n    return json\n", "IMPORT_SCOPE_UNSUPPORTED"),
    ],
)
def test_remove_import_json_refuses_expected_errors(
    tmp_path: Path, monkeypatch, capsys, content: str, expected_code: str
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, content)
    init_git_repo(root)

    exit_code = main(
        [
            "remove-import",
            str(sample),
            "--expect-statement",
            "import json",
            "--format",
            "json",
        ]
    )

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["status"] == "refused"
    assert payload["error"]["code"] == expected_code
    assert payload["result"] is None
    assert git_status_short(root) == ""


@pytest.mark.parametrize(
    "content",
    [
        b"import json\nVALUE = 1\n",
        b"import json\r\nVALUE = 1\r\n",
        b"\xef\xbb\xbfimport json\nVALUE = 1\n",
        b"import json\nVALUE = 1",
    ],
)
def test_remove_import_rollback_restores_exact_bytes(
    tmp_path: Path, monkeypatch, content: bytes
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_bytes_sample(root, content)
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"
    original = sample.read_bytes()

    result = remove_import(sample, "import json", project_root=root, db_path=db_path)
    assert result.operation_id is not None
    commit_all(root, "apply import removal")

    rollback_last(db_path)

    assert sample.read_bytes() == original
    assert git_status_short(root) != ""


def test_remove_import_rollback_by_id_restores_and_blocks_second_rollback(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "import json\nVALUE = 1\n")
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"
    original = sample.read_bytes()

    result = remove_import(sample, "import json", project_root=root, db_path=db_path)
    operation_id = result.operation_id
    assert operation_id is not None
    commit_all(root, "apply import removal")

    rollback_by_id(db_path, operation_id, current_root=root)
    commit_all(root, "apply rollback")

    assert sample.read_bytes() == original
    with pytest.raises(GitError):
        rollback_by_id(db_path, operation_id, current_root=root)


def test_remove_import_by_id_selects_the_requested_operation_only(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    file_a = root / "a.py"
    file_b = root / "b.py"
    file_c = root / "c.py"
    file_a.write_text("import json\nVALUE_A = 1\n", encoding="utf-8")
    file_b.write_text("import numpy as np\nVALUE_B = 2\n", encoding="utf-8")
    file_c.write_text("from pathlib import Path\nVALUE_C = 3\n", encoding="utf-8")
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"
    original_a = file_a.read_bytes()
    original_b = file_b.read_bytes()
    original_c = file_c.read_bytes()

    result_a = remove_import(file_a, "import json", project_root=root, db_path=db_path)
    commit_all(root, "apply removal a")
    removed_a = file_a.read_bytes()
    result_b = remove_import(file_b, "import numpy as np", project_root=root, db_path=db_path)
    commit_all(root, "apply removal b")
    removed_b = file_b.read_bytes()
    result_c = remove_import(file_c, "from pathlib import Path", project_root=root, db_path=db_path)
    commit_all(root, "apply removal c")
    removed_c = file_c.read_bytes()

    assert result_a.operation_id and result_b.operation_id and result_c.operation_id

    rollback_by_id(db_path, result_b.operation_id, current_root=root)

    assert file_a.read_bytes() == removed_a
    assert file_b.read_bytes() == original_b
    assert file_c.read_bytes() == removed_c
