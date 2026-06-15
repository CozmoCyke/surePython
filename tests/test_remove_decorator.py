from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

import surepython.codemods as codemods
from surepython.cli import main
from surepython.codemods import add_decorator, add_import, remove_decorator
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
            SELECT
                operation,
                status,
                symbol,
                decorator_expression,
                decorator_position,
                decorator_target_kind,
                expected_decorator_expression,
                expected_decorator_position,
                removed_decorator_expression,
                removed_decorator_position,
                source_operation_id
            FROM surepython_operations
            ORDER BY id
            """
        ).fetchall()


def latest_operation_id(db_path: Path) -> int:
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


def test_remove_decorator_supports_outermost_and_innermost_positions(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root_outer = tmp_path / "project_outer"
    root_outer.mkdir()
    sample_outer = write_sample(
        root_outer,
        "@third\n"
        "@first  # wrapper externe\n"
        "@second\n"
        "def run():\n"
        "    return 1\n",
    )
    init_git_repo(root_outer)

    remove_decorator(sample_outer, "run", "third", "outermost", project_root=root_outer)
    assert sample_outer.read_text(encoding="utf-8").startswith("@first  # wrapper externe\n@second\n")

    root_inner = tmp_path / "project_inner"
    root_inner.mkdir()
    sample_inner = write_sample(
        root_inner,
        "@first  # wrapper externe\n"
        "@second\n"
        "@third\n"
        "def run():\n"
        "    return 1\n",
    )
    init_git_repo(root_inner)

    remove_decorator(sample_inner, "run", "third", "innermost", project_root=root_inner)
    assert sample_inner.read_text(encoding="utf-8").startswith("@first  # wrapper externe\n@second\n")


def test_remove_decorator_supports_duplicate_edge_occurrences_and_multiline_blocks(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(
        root,
        "@cached\n"
        "@other  # keep me\n"
        "@decorator(\n"
        "    option=True,\n"
        "    values=[1, 2],\n"
        ")\n"
        "@cached\n"
        "def run():\n"
        "    return 1\n",
    )
    init_git_repo(root)

    remove_decorator(sample, "run", "cached", "outermost", project_root=root)
    assert sample.read_text(encoding="utf-8").startswith("@other  # keep me\n@decorator(\n")
    assert sample.read_text(encoding="utf-8").endswith("@cached\ndef run():\n    return 1\n")

    root_inner = tmp_path / "project_inner"
    root_inner.mkdir()
    sample_inner = write_sample(
        root_inner,
        "@cached\n"
        "@other  # keep me\n"
        "@decorator(\n"
        "    option=True,\n"
        "    values=[1, 2],\n"
        ")\n"
        "@cached\n"
        "def run():\n"
        "    return 1\n",
    )
    init_git_repo(root_inner)

    remove_decorator(sample_inner, "run", "cached", "innermost", project_root=root_inner)
    text = sample_inner.read_text(encoding="utf-8")
    assert text.startswith("@cached\n@other  # keep me\n@decorator(\n")
    assert "values=[1, 2]," in text


@pytest.mark.parametrize(
    "source,target,expected_decorator,expected_position,needle",
    [
        (
            "class Service:\n"
            "    @classmethod\n"
            "    @cached\n"
            "    def build(cls):\n"
            "        return cls()\n",
            "Service.build",
            "classmethod",
            "outermost",
            "    @cached\n    def build(cls):",
        ),
        (
            "@retry\n"
            "async def fetch():\n"
            "    return 1\n",
            "fetch",
            "retry",
            "outermost",
            "async def fetch():\n",
        ),
        (
            "@dataclass(frozen=True)\n"
            "@registered\n"
            "class User(Base, metaclass=Meta):\n"
            "    \"\"\"User model.\"\"\"\n"
            "    value = 1\n",
            "User",
            "registered",
            "innermost",
            "class User(Base, metaclass=Meta):\n    \"\"\"User model.\"\"\"\n    value = 1\n",
        ),
    ],
)
def test_remove_decorator_supports_methods_classes_and_async_functions(
    tmp_path: Path,
    monkeypatch,
    source: str,
    target: str,
    expected_decorator: str,
    expected_position: str,
    needle: str,
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, source)
    init_git_repo(root)

    result = remove_decorator(sample, target, expected_decorator, expected_position, project_root=root)

    assert result.status == "applied"
    assert result.removed_decorator.replace(" ", "") == expected_decorator.replace(" ", "")
    assert needle in sample.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "source,target,expected_decorator,expected_position,code",
    [
        ("def run():\n    return 1\n", "run", "staticmethod", "outermost", "DECORATOR_NOT_FOUND"),
        ("@first\n@second\n@third\ndef run():\n    return 1\n", "run", "second", "outermost", "DECORATOR_POSITION_MISMATCH"),
        ("@cached\ndef run():\n    return 1\n", "missing", "cached", "outermost", "TARGET_NOT_FOUND"),
        (
            "class A:\n    @cached\n    def load(self):\n        return 1\n\n"
            "class B:\n    @cached\n    def load(self):\n        return 2\n",
            "load",
            "cached",
            "outermost",
            "TARGET_AMBIGUOUS",
        ),
    ],
)
def test_remove_decorator_refuses_expected_decorator_and_symbol_mismatches(
    tmp_path: Path,
    monkeypatch,
    source: str,
    target: str,
    expected_decorator: str,
    expected_position: str,
    code: str,
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, source)
    init_git_repo(root)

    with pytest.raises(GitError) as excinfo:
        remove_decorator(sample, target, expected_decorator, expected_position, project_root=root)

    assert excinfo.value.code == code
    assert git_status_short(root) == ""


def test_remove_decorator_json_dry_run_is_structured_and_quiet(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(
        root,
        "@first\n"
        "@second\n"
        "def run():\n"
        "    return 1\n",
    )
    init_git_repo(root)
    before = sample.read_text(encoding="utf-8")

    exit_code = main(
        [
            "remove-decorator",
            str(sample),
            "--symbol",
            "run",
            "--expect-decorator",
            "first",
            "--expect-position",
            "outermost",
            "--dry-run",
            "--format",
            "json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["protocol_schema_version"] == "1.0"
    assert payload["command"] == "remove-decorator"
    assert payload["ok"] is True
    assert payload["status"] == "preview"
    assert payload["error"] is None
    assert payload["result"]["expected_decorator"] == "first"
    assert payload["result"]["expected_position"] == "outermost"
    assert payload["result"]["removed_decorator"] == "first"
    assert payload["result"]["removed_position"] == "outermost"
    assert payload["result"]["target"]["symbol"] == "run"
    assert payload["result"]["target"]["kind"] == "function"
    assert payload["result"]["written"] is False
    assert payload["result"]["logged"] is False
    assert payload["result"]["rollback_available"] is False
    assert payload["result"]["operation_id"] is None
    assert sample.read_text(encoding="utf-8") == before
    assert git_status_short(root) == ""


@pytest.mark.parametrize(
    "extra_args, expected_code",
    [
        (["--expect-position", "outermost", "--format", "json"], "DECORATOR_REQUIRED"),
        (["--expect-decorator", "first", "--format", "json"], "DECORATOR_POSITION_REQUIRED"),
        (["--expect-decorator", "first", "--expect-position", "middle", "--format", "json"], "DECORATOR_POSITION_INVALID"),
    ],
)
def test_remove_decorator_json_refusal_is_pure_json(
    tmp_path: Path, monkeypatch, capsys, extra_args: list[str], expected_code: str
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def run():\n    return 1\n")
    init_git_repo(root)

    exit_code = main(["remove-decorator", str(sample), "--symbol", "run", *extra_args])

    assert exit_code != 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"]["code"] == expected_code
    assert payload["result"] is None
    assert git_status_short(root) == ""


def test_remove_decorator_application_logs_operation_and_supports_rollback_by_id(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(
        root,
        "@classmethod\n"
        "@cached\n"
        "def build(cls):\n"
        "    return cls()\n",
    )
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"
    monkeypatch.setattr(codemods, "run_pytest", lambda cwd, command=None: (0, "ok"))

    exit_code = main(
        [
            "remove-decorator",
            str(sample),
            "--symbol",
            "build",
            "--expect-decorator",
            "classmethod",
            "--expect-position",
            "outermost",
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
    assert payload["result"]["expected_decorator"] == "classmethod"
    assert payload["result"]["removed_decorator"] == "classmethod"
    assert payload["result"]["target"]["kind"] == "function"
    assert payload["result"]["operation_id"] is not None
    assert payload["result"]["logged"] is True
    assert payload["result"]["rollback_available"] is True
    assert payload["result"]["tests"]["status"] == "passed"
    assert payload["result"]["tests"]["exit_code"] == 0
    assert "@cached\n" in sample.read_text(encoding="utf-8")
    rows = read_rows(db_path)
    assert rows[0][:6] == (
        "remove-decorator",
        "tested",
        "build",
        "classmethod",
        "outermost",
        "function",
    )

    commit_all(root, "apply decorator removal")
    operation_id = latest_operation_id(db_path)
    result = rollback_by_id(db_path, operation_id, current_root=root)

    assert result.status == "rolled_back"
    assert "@classmethod\n" in sample.read_text(encoding="utf-8")
    assert read_rows(db_path)[-1][0] == "rollback"
    assert read_rows(db_path)[-1][10] == operation_id


@pytest.mark.parametrize(
    "content",
    [
        b"@classmethod\n@cached\ndef build(cls):\n    return cls()\n",
        b"@classmethod\r\n@cached\r\ndef build(cls):\r\n    return cls()\r\n",
        b"\xef\xbb\xbf@classmethod\n@cached\ndef build(cls):\n    return cls()\n",
        b"@classmethod\n@cached\ndef build(cls):\n    return cls()",
    ],
)
def test_remove_decorator_rollback_restores_exact_bytes(
    tmp_path: Path, monkeypatch, content: bytes
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, content)
    original = sample.read_bytes()
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"

    remove_decorator(sample, "build", "classmethod", "outermost", project_root=root, db_path=db_path)
    commit_all(root, "apply decorator removal")
    operation_id = latest_operation_id(db_path)

    result = rollback_by_id(db_path, operation_id, current_root=root)

    assert result.status == "rolled_back"
    assert sample.read_bytes() == original


def test_remove_decorator_double_rollback_is_refused_after_commit(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(
        root,
        "@classmethod\n"
        "@cached\n"
        "def build(cls):\n"
        "    return cls()\n",
    )
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"

    remove_decorator(sample, "build", "classmethod", "outermost", project_root=root, db_path=db_path)
    commit_all(root, "apply decorator removal")
    operation_id = latest_operation_id(db_path)
    rollback_by_id(db_path, operation_id, current_root=root)
    commit_all(root, "apply rollback")

    with pytest.raises(GitError, match="already been rolled back"):
        rollback_by_id(db_path, operation_id, current_root=root)


def test_remove_decorator_composes_with_add_decorator_and_add_import(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def calculate():\n    return 1\n")
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"
    monkeypatch.setattr(codemods, "run_pytest", lambda cwd, command=None: (0, "ok"))

    import_result = add_import(sample, "from functools import cached_property", project_root=root, db_path=db_path)
    commit_all(root, "add import")
    decorator_result = add_decorator(
        sample,
        "calculate",
        "staticmethod",
        "outermost",
        project_root=root,
        db_path=db_path,
    )
    commit_all(root, "add decorator")
    removal_result = remove_decorator(
        sample,
        "calculate",
        "staticmethod",
        "outermost",
        project_root=root,
        db_path=db_path,
    )
    commit_all(root, "remove decorator")

    assert import_result.operation_id is not None
    assert decorator_result.operation_id is not None
    assert removal_result.operation_id is not None
    assert "from functools import cached_property" in sample.read_text(encoding="utf-8")
    assert "@staticmethod" not in sample.read_text(encoding="utf-8")

    rollback_by_id(db_path, removal_result.operation_id, current_root=root)
    commit_all(root, "rollback removal")
    assert "@staticmethod" in sample.read_text(encoding="utf-8")

    rollback_by_id(db_path, decorator_result.operation_id, current_root=root)
    commit_all(root, "rollback decorator")
    assert "@staticmethod" not in sample.read_text(encoding="utf-8")
    assert "from functools import cached_property" in sample.read_text(encoding="utf-8")
