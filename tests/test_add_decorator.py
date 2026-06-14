from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

import surepython.codemods as codemods
from surepython.cli import main
from surepython.codemods import add_decorator, add_import, add_return_type
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
            SELECT operation, status, symbol, decorator_expression, decorator_position, decorator_target_kind, source_operation_id
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


def test_add_decorator_supports_outermost_and_innermost_positions(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root_outer = tmp_path / "project_outer"
    root_outer.mkdir()
    sample_outer = write_sample(
        root_outer,
        "@first  # wrapper externe\n"
        "@second\n"
        "def run():\n"
        "    return 1\n",
    )
    init_git_repo(root_outer)

    add_decorator(sample_outer, "run", "new_decorator", "outermost", project_root=root_outer)
    outer_text = sample_outer.read_text(encoding="utf-8")
    assert outer_text.startswith("@new_decorator\n@first  # wrapper externe\n@second\n")

    root_inner = tmp_path / "project_inner"
    root_inner.mkdir()
    sample_inner = write_sample(
        root_inner,
        "@first  # wrapper externe\n"
        "@second\n"
        "def run():\n"
        "    return 1\n",
    )
    init_git_repo(root_inner)

    add_decorator(sample_inner, "run", "new_decorator", "innermost", project_root=root_inner)
    inner_text = sample_inner.read_text(encoding="utf-8")
    assert inner_text.startswith("@first  # wrapper externe\n@second\n@new_decorator\n")


def test_add_decorator_supports_classes_and_async_functions(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root_class = tmp_path / "project_class"
    root_class.mkdir()
    sample_class = write_sample(
        root_class,
        "class Outer:\n"
        "    class Inner:\n"
        "        pass\n\n"
    )
    init_git_repo(root_class)

    add_decorator(sample_class, "Outer.Inner", "dataclass(frozen=True)", "outermost", project_root=root_class)
    assert "    @dataclass(frozen=True)\n    class Inner:" in sample_class.read_text(encoding="utf-8")

    root_async = tmp_path / "project_async"
    root_async.mkdir()
    sample_async = write_sample(
        root_async,
        "async def fetch():\n"
        "    return 1\n",
    )
    init_git_repo(root_async)

    add_decorator(sample_async, "fetch", "staticmethod", "outermost", project_root=root_async)
    assert "@staticmethod\nasync def fetch" in sample_async.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "decorator",
    [
        "",
        "@staticmethod",
        "staticmethod\nclassmethod",
        "lambda f: f",
        "a + b",
        "await decorator()",
        "decorator(",
    ],
)
def test_add_decorator_refuses_invalid_expressions(tmp_path: Path, monkeypatch, decorator: str) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def run():\n    return 1\n")
    init_git_repo(root)

    with pytest.raises(GitError):
        add_decorator(sample, "run", decorator, "outermost", project_root=root)


def test_add_decorator_refuses_duplicates_and_conflicts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(
        root,
        "@dataclass(frozen=True)\n"
        "class User:\n"
        "    pass\n\n"
        "@staticmethod\n"
        "def build():\n"
        "    return 1\n",
    )
    init_git_repo(root)

    with pytest.raises(GitError, match="already exists"):
        add_decorator(sample, "User", "dataclass(frozen=True)", "outermost", project_root=root)

    with pytest.raises(GitError, match="conflicts"):
        add_decorator(sample, "build", "classmethod", "outermost", project_root=root)


def test_add_decorator_json_dry_run_is_structured_and_quiet(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def run():\n    return 1\n")
    init_git_repo(root)
    before = sample.read_text(encoding="utf-8")

    exit_code = main(
        [
            "add-decorator",
            str(sample),
            "--symbol",
            "run",
            "--decorator",
            "staticmethod",
            "--position",
            "outermost",
            "--dry-run",
            "--format",
            "json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["protocol_schema_version"] == "1.0"
    assert payload["command"] == "add-decorator"
    assert payload["ok"] is True
    assert payload["status"] == "preview"
    assert payload["error"] is None
    assert payload["result"]["decorator"] == "staticmethod"
    assert payload["result"]["position"] == "outermost"
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
        (["--decorator", "staticmethod", "--format", "json"], "DECORATOR_POSITION_REQUIRED"),
        (["--position", "outermost", "--format", "json"], "DECORATOR_REQUIRED"),
        (["--decorator", "staticmethod", "--position", "middle", "--format", "json"], "DECORATOR_POSITION_INVALID"),
    ],
)
def test_add_decorator_json_refusal_is_pure_json(
    tmp_path: Path, monkeypatch, capsys, extra_args: list[str], expected_code: str
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def run():\n    return 1\n")
    init_git_repo(root)

    exit_code = main(["add-decorator", str(sample), "--symbol", "run", *extra_args])

    assert exit_code != 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"]["code"] == expected_code
    assert payload["result"] is None
    assert git_status_short(root) == ""


def test_add_decorator_application_logs_operation_and_supports_rollback_by_id(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def run():\n    return 1\n")
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"
    monkeypatch.setattr(codemods, "run_pytest", lambda cwd, command=None: (0, "ok"))

    exit_code = main(
        [
            "add-decorator",
            str(sample),
            "--symbol",
            "run",
            "--decorator",
            "staticmethod",
            "--position",
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
    assert payload["result"]["decorator"] == "staticmethod"
    assert payload["result"]["position"] == "outermost"
    assert payload["result"]["target"]["kind"] == "function"
    assert payload["result"]["operation_id"] is not None
    assert payload["result"]["logged"] is True
    assert payload["result"]["rollback_available"] is True
    assert payload["result"]["tests"]["status"] == "passed"
    assert payload["result"]["tests"]["exit_code"] == 0
    assert "@staticmethod\n" in sample.read_text(encoding="utf-8")
    assert read_rows(db_path)[0][:6] == (
        "add-decorator",
        "tested",
        "run",
        "staticmethod",
        "outermost",
        "function",
    )

    commit_all(root, "apply decorator")
    operation_id = latest_operation_id(db_path)
    result = rollback_by_id(db_path, operation_id, current_root=root)

    assert result.status == "rolled_back"
    assert "@staticmethod\n" not in sample.read_text(encoding="utf-8")
    assert read_rows(db_path)[-1][0] == "rollback"
    assert read_rows(db_path)[-1][6] == operation_id


@pytest.mark.parametrize(
    "content",
    [
        b"def run():\n    return 1\n",
        b"def run():\r\n    return 1\r\n",
        b"\xef\xbb\xbfdef run():\n    return 1\n",
        b"def run():\n    return 1",
    ],
)
def test_add_decorator_rollback_restores_exact_bytes(
    tmp_path: Path, monkeypatch, content: bytes
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_bytes_sample(root, content)
    original = sample.read_bytes()
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"

    add_decorator(sample, "run", "staticmethod", "outermost", project_root=root, db_path=db_path)
    commit_all(root, "apply decorator")

    result = rollback_last(db_path)

    assert result.status == "rolled_back"
    assert sample.read_bytes() == original
    assert git_status_short(root) != ""


def test_add_decorator_double_rollback_is_refused_after_commit(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def run():\n    return 1\n")
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"

    add_decorator(sample, "run", "staticmethod", "outermost", project_root=root, db_path=db_path)
    commit_all(root, "apply decorator")
    operation_id = latest_operation_id(db_path)
    rollback_by_id(db_path, operation_id, current_root=root)
    commit_all(root, "apply rollback")

    with pytest.raises(GitError, match="already been rolled back"):
        rollback_by_id(db_path, operation_id, current_root=root)


def test_add_decorator_composes_with_add_import_and_add_return_type(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def calculate(value):\n    return value\n")
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"
    monkeypatch.setattr(codemods, "run_pytest", lambda cwd, command=None: (0, "ok"))

    import_result = add_import(sample, "from functools import lru_cache", project_root=root, db_path=db_path)
    commit_all(root, "add import")
    decorator_result = add_decorator(
        sample,
        "calculate",
        "lru_cache(maxsize=128)",
        "outermost",
        project_root=root,
        db_path=db_path,
    )
    commit_all(root, "add decorator")
    return_result = add_return_type(sample, "calculate", "int", project_root=root, db_path=db_path)
    commit_all(root, "add return type")

    assert "from functools import lru_cache" in sample.read_text(encoding="utf-8")
    assert "@lru_cache(maxsize=128)" in sample.read_text(encoding="utf-8")
    assert "-> int" in sample.read_text(encoding="utf-8")

    assert import_result.operation_id is not None
    assert decorator_result.operation_id is not None
    assert return_result.operation_id is not None

    rollback_by_id(db_path, return_result.operation_id, current_root=root)
    commit_all(root, "rollback return type")
    assert "-> int" not in sample.read_text(encoding="utf-8")
    assert "@lru_cache(maxsize=128)" in sample.read_text(encoding="utf-8")

    rollback_by_id(db_path, decorator_result.operation_id, current_root=root)
    commit_all(root, "rollback decorator")
    assert "@lru_cache(maxsize=128)" not in sample.read_text(encoding="utf-8")
    assert "from functools import lru_cache" in sample.read_text(encoding="utf-8")
