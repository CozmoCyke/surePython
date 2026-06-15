from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

import surepython.codemods as codemods
from surepython.cli import main
from surepython.codemods import add_import, add_parameter_type, add_return_type, remove_parameter_type
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
            SELECT operation, status, symbol, parameter, target_kind, parameter_kind,
                   expected_parameter_annotation, parameter_annotation,
                   before_sha256, after_sha256, pytest_status, source_operation_id
            FROM surepython_operations
            ORDER BY id
            """
        ).fetchall()


def write_sample(root: Path, content: bytes | str) -> Path:
    sample = root / "sample.py"
    if isinstance(content, bytes):
        sample.write_bytes(content)
    else:
        sample.write_text(content, encoding="utf-8")
    return sample


def test_remove_parameter_type_to_simple_function(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def calculate(value: int):\n    return value\n")
    init_git_repo(root)

    result = remove_parameter_type(sample, "calculate", "value", "int", project_root=root)

    assert result.status == "applied"
    assert result.removed_annotation == "int"
    assert "def calculate(value):" in sample.read_text(encoding="utf-8")


def test_remove_parameter_type_to_method_only(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(
        root,
        "def calculate(value: int):\n"
        "    return value\n\n"
        "class Service:\n"
        "    def calculate(self, value: int):\n"
        "        return value\n",
    )
    init_git_repo(root)

    remove_parameter_type(sample, "Service.calculate", "value", "int", project_root=root)
    updated = sample.read_text(encoding="utf-8")

    assert "def calculate(value: int):" in updated
    assert "def calculate(self, value):" in updated


def test_remove_parameter_type_supports_async_function(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "async def fetch(source: Path):\n    return source\n")
    init_git_repo(root)

    result = remove_parameter_type(sample, "fetch", "source", "Path", project_root=root)

    assert result.status == "applied"
    assert "async def fetch(source):" in sample.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("source", "target", "parameter", "expected_annotation", "needle"),
    [
        ("def f(value: int, /, other: str = 'x'):\n    return value\n", "f", "value", "int", "def f(value, /, other: str = 'x'):" ),
        ("def f(*, value: int = 1, enabled: bool = True):\n    return value\n", "f", "value", "int", "def f(*, value = 1, enabled: bool = True):"),
        ("class Service:\n    def run(self: 'Service', value: int):\n        return value\n", "Service.run", "self", "'Service'", "def run(self, value: int):"),
        ("class Service:\n    @classmethod\n    def build(cls: type['Service'], value: int):\n        return value\n", "Service.build", "cls", "type['Service']", "def build(cls, value: int):"),
    ],
)
def test_remove_parameter_type_preserves_signature_shapes(
    tmp_path: Path,
    monkeypatch,
    source: str,
    target: str,
    parameter: str,
    expected_annotation: str,
    needle: str,
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, source)
    init_git_repo(root)

    remove_parameter_type(sample, target, parameter, expected_annotation, project_root=root)

    assert needle in sample.read_text(encoding="utf-8")


def test_remove_parameter_type_preserves_multiline_signature_and_comment(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(
        root,
        "def render(\n"
        "    source: dict[str, int],\n"
        "    /,\n"
        "    *,\n"
        "    enabled: bool = True,  # keep comment\n"
        ") -> str:\n"
        "    return 'ok'\n",
    )
    init_git_repo(root)

    remove_parameter_type(sample, "render", "source", "dict[str, int]", project_root=root)
    updated = sample.read_text(encoding="utf-8")

    assert "source:" not in updated
    assert "enabled: bool = True,  # keep comment" in updated
    assert ") -> str:" in updated


def test_remove_parameter_type_dry_run_json_is_preview_and_quiet(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def calculate(value: int):\n    return value\n")
    init_git_repo(root)
    before = sample.read_bytes()

    exit_code = main(
        [
            "remove-parameter-type",
            str(sample),
            "--function",
            "calculate",
            "--parameter",
            "value",
            "--expect-annotation",
            "int",
            "--dry-run",
            "--format",
            "json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["protocol_schema_version"] == "1.0"
    assert payload["command"] == "remove-parameter-type"
    assert payload["ok"] is True
    assert payload["status"] == "preview"
    assert payload["result"]["target"]["kind"] == "function"
    assert payload["result"]["target"]["parameter"] == "value"
    assert payload["result"]["parameter_kind"] == "positional_or_keyword"
    assert payload["result"]["expected_annotation"] == "int"
    assert payload["result"]["removed_annotation"] == "int"
    assert payload["result"]["written"] is False
    assert payload["result"]["logged"] is False
    assert payload["result"]["rollback_available"] is False
    assert payload["result"]["operation_id"] is None
    assert sample.read_bytes() == before
    assert git_status_short(root) == ""


def test_remove_parameter_type_json_application_includes_operation_id_and_tests(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def calculate(value: int):\n    return value\n")
    tests_dir = root / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_smoke.py").write_text(
        "from sample import calculate\n\n"
        "def test_smoke():\n"
        "    assert calculate(3) == 3\n",
        encoding="utf-8",
    )
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"
    monkeypatch.setattr(codemods, "run_pytest", lambda cwd, command=None: (0, "ok"))

    exit_code = main(
        [
            "remove-parameter-type",
            str(sample),
            "--function",
            "calculate",
            "--parameter",
            "value",
            "--expect-annotation",
            "int",
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
    assert payload["result"]["parameter_kind"] == "positional_or_keyword"
    assert payload["result"]["removed_annotation"] == "int"
    assert payload["result"]["tests"]["status"] == "passed"
    row = read_rows(db_path)[0]
    assert row[0] == "remove-parameter-type"
    assert row[1] == "tested"
    assert row[2] == "calculate"
    assert row[3] == "value"
    assert row[4] == "function"
    assert row[5] == "positional_or_keyword"
    assert row[6] == "int"
    assert row[7] == "int"


def test_remove_parameter_type_refuses_annotation_mismatch_json(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def calculate(value: int):\n    return value\n")
    init_git_repo(root)
    before = sample.read_text(encoding="utf-8")

    exit_code = main(
        [
            "remove-parameter-type",
            str(sample),
            "--function",
            "calculate",
            "--parameter",
            "value",
            "--expect-annotation",
            "str",
            "--format",
            "json",
        ]
    )

    assert exit_code != 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["result"] is None
    assert payload["error"]["code"] == "PARAMETER_ANNOTATION_MISMATCH"
    assert payload["error"]["details"]["expected_annotation"] == "str"
    assert payload["error"]["details"]["actual_annotation"] == "int"
    assert sample.read_text(encoding="utf-8") == before


@pytest.mark.parametrize("expected", ["", "str |", "list["])
def test_remove_parameter_type_refuses_invalid_expected_annotation(
    tmp_path: Path, monkeypatch, expected: str
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def calculate(value: int):\n    return value\n")
    init_git_repo(root)

    with pytest.raises(GitError):
        remove_parameter_type(sample, "calculate", "value", expected, project_root=root)


def test_remove_parameter_type_refuses_missing_parameter(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def calculate(value: int):\n    return value\n")
    init_git_repo(root)

    with pytest.raises(GitError, match="Target parameter not found"):
        remove_parameter_type(sample, "calculate", "source", "int", project_root=root)


def test_remove_parameter_type_refuses_missing_annotation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def calculate(value):\n    return value\n")
    init_git_repo(root)

    with pytest.raises(GitError, match="does not contain an annotation"):
        remove_parameter_type(sample, "calculate", "value", "int", project_root=root)


def test_remove_parameter_type_refuses_variadic_parameters(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def calculate(*args: str, **kwargs: object):\n    return args\n")
    init_git_repo(root)

    with pytest.raises(GitError, match="Variadic positional"):
        remove_parameter_type(sample, "calculate", "args", "str", project_root=root)
    with pytest.raises(GitError, match="Variadic keyword"):
        remove_parameter_type(sample, "calculate", "kwargs", "object", project_root=root)


def test_remove_parameter_type_refuses_symbol_absent(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def calculate(value: int):\n    return value\n")
    init_git_repo(root)

    with pytest.raises(GitError, match="Target symbol not found"):
        remove_parameter_type(sample, "missing", "value", "int", project_root=root)


def test_remove_parameter_type_refuses_target_unsupported(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "class Service:\n    pass\n")
    init_git_repo(root)

    with pytest.raises(GitError, match="Target symbol not found"):
        remove_parameter_type(sample, "Service", "value", "int", project_root=root)


def test_remove_parameter_type_rollback_by_id_restores_bytes_exactly(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = root / "sample.py"
    original = b"\xef\xbb\xbfdef calculate(value: int = 1) -> int:\r\n    return value\r\n"
    sample.write_bytes(original)
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"

    result = remove_parameter_type(sample, "calculate", "value", "int", project_root=root, db_path=db_path)
    commit_all(root, "remove parameter annotation")
    rollback_by_id(db_path, result.operation_id or 0, current_root=root)
    commit_all(root, "restore parameter annotation")

    assert sample.read_bytes() == original


def test_remove_parameter_type_rollback_last_restores_annotation(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def calculate(value: int):\n    return value\n")
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"

    result = remove_parameter_type(sample, "calculate", "value", "int", project_root=root, db_path=db_path)
    commit_all(root, "remove parameter annotation")
    rollback_last(db_path)

    assert result.operation_id is not None
    assert sample.read_text(encoding="utf-8") == "def calculate(value: int):\n    return value\n"


def test_remove_parameter_type_double_rollback_refused(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def calculate(value: int):\n    return value\n")
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"

    result = remove_parameter_type(sample, "calculate", "value", "int", project_root=root, db_path=db_path)
    commit_all(root, "remove parameter annotation")
    rollback_by_id(db_path, result.operation_id or 0, current_root=root)
    commit_all(root, "restore parameter annotation")

    with pytest.raises(GitError, match="already been rolled back"):
        rollback_by_id(db_path, result.operation_id or 0, current_root=root)


def test_remove_parameter_type_composes_with_add_parameter_type(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def calculate(value=1):\n    return value\n")
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"

    add_parameter_type(sample, "calculate", "value", "int", project_root=root, db_path=db_path)
    commit_all(root, "add parameter annotation")
    remove_parameter_type(sample, "calculate", "value", "int", project_root=root, db_path=db_path)
    commit_all(root, "remove parameter annotation")

    assert sample.read_text(encoding="utf-8") == "def calculate(value=1):\n    return value\n"


def test_remove_parameter_type_composes_with_import_and_return_type(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_sample(root, "def parse(source):\n    return source\n")
    init_git_repo(root)
    db_path = tmp_path / "surepython.db"

    add_import(sample, "from pathlib import Path", project_root=root, db_path=db_path)
    commit_all(root, "add import")
    add_parameter_type(sample, "parse", "source", "Path", project_root=root, db_path=db_path)
    commit_all(root, "add parameter annotation")
    add_return_type(sample, "parse", "Path", project_root=root, db_path=db_path)
    commit_all(root, "add annotations")
    remove_parameter_type(sample, "parse", "source", "Path", project_root=root, db_path=db_path)
    commit_all(root, "remove parameter annotation")

    assert "from pathlib import Path" in sample.read_text(encoding="utf-8")
    assert "def parse(source) -> Path:" in sample.read_text(encoding="utf-8")
