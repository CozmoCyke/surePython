from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import tempfile
from argparse import _SubParsersAction
from pathlib import Path
from typing import Any

from .capabilities import serialize_capabilities
from .datasette_log import ensure_schema
from .plans import (
    PLAN_MAX_STEPS,
    PLAN_SCHEMA_VERSION,
    SUPPORTED_PLAN_OPERATIONS,
    TRANSACTION_MANIFEST_ALLOWED_STATUSES,
    TRANSACTION_MANIFEST_INITIAL_STATUSES,
    TRANSACTION_MANIFEST_SCHEMA_VERSION,
    TRANSACTION_MANIFEST_TRANSITIONS,
)
from .protocol import CAPABILITIES_SCHEMA_VERSION, ERROR_CODES, EXIT_CODE_BY_ERROR_CODE, PROTOCOL_SCHEMA_VERSION


_RETRYABLE_ERROR_CODES = {
    "PROJECT_MUTATION_LOCKED",
    "DATABASE_ERROR",
    "PLAN_DATABASE_FAILED",
    "INTERNAL_ERROR",
}

_PROJECT_MODIFIED_ERROR_CODES = {
    "PLAN_STEP_FAILED",
    "PLAN_TESTS_FAILED",
    "PLAN_DATABASE_FAILED",
    "DATABASE_ERROR",
    "INTERNAL_ERROR",
    "PLAN_RECOVERY_REQUIRED",
}

_RECOVERY_REQUIRED_ERROR_CODES = {
    "PLAN_RECOVERY_REQUIRED",
    "PLAN_MANIFEST_INVALID",
    "PLAN_RECOVERY_CONFLICT",
}


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if callable(value):
        return getattr(value, "__name__", repr(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(_jsonable(value), indent=2, ensure_ascii=False, sort_keys=True)


def _serialize_action(action: argparse.Action) -> dict[str, Any]:
    return {
        "kind": action.__class__.__name__,
        "dest": action.dest,
        "option_strings": list(action.option_strings),
        "required": bool(getattr(action, "required", False)),
        "default": _jsonable(action.default),
        "choices": sorted(_jsonable(list(action.choices))) if getattr(action, "choices", None) is not None else None,
        "nargs": action.nargs,
    }


def build_cli_contract_tree(parser: argparse.ArgumentParser) -> dict[str, Any]:
    tree: dict[str, Any] = {
        "prog": parser.prog,
        "description": parser.description,
        "actions": [],
    }
    for action in parser._actions:
        if isinstance(action, _SubParsersAction):
            tree["actions"].append(
                {
                    "kind": "subparsers",
                    "dest": action.dest,
                    "required": action.required,
                    "choices": sorted(action.choices),
                    "parsers": {
                        name: build_cli_contract_tree(subparser)
                        for name, subparser in sorted(action.choices.items())
                    },
                }
            )
            continue
        tree["actions"].append(_serialize_action(action))
    return tree


def build_cli_contract() -> dict[str, Any]:
    from .cli import build_parser

    parser = build_parser()
    return {
        "contract_version": "1.0",
        "prog": parser.prog,
        "description": parser.description,
        "tree": build_cli_contract_tree(parser),
    }


def _load_capabilities_payload() -> dict[str, Any]:
    return json.loads(serialize_capabilities("json"))


def build_capabilities_contract() -> dict[str, Any]:
    return _load_capabilities_payload()


def _error_category(code: str) -> str:
    if code.startswith("GIT_"):
        return "git"
    if code.startswith("FILE_"):
        return "filesystem"
    if code.startswith("DOCSTRING_"):
        return "docstring"
    if code.startswith("ANNOTATION_") or code.startswith("RETURN_"):
        return "annotation"
    if code.startswith("PARAMETER_"):
        return "parameter"
    if code.startswith("DECORATOR_"):
        return "decorator"
    if code.startswith("IMPORT_"):
        return "import"
    if code.startswith("ROLLBACK_"):
        return "rollback"
    if code.startswith("PLAN_"):
        return "plan"
    if code in {"HASH_MISMATCH", "LEGACY_UNVERIFIABLE", "PROJECT_MISMATCH"}:
        return "security"
    if code in {"DATABASE_ERROR", "PLAN_DATABASE_FAILED"}:
        return "storage"
    if code in {"TESTS_FAILED", "PLAN_TESTS_FAILED"}:
        return "tests"
    if code in {"INTERNAL_ERROR"}:
        return "internal"
    return "general"


def _error_description(code: str) -> str:
    words = code.lower().replace("_", " ")
    return words[:1].upper() + words[1:]


def _commands_for_error(code: str) -> list[str]:
    payload = _load_capabilities_payload()
    commands: set[str] = set()
    for operation in payload["operations"]:
        if code in operation["possible_error_codes"]:
            commands.add(operation["name"])
    for command in payload.get("commands", []):
        if code in command["possible_error_codes"]:
            commands.add(command["name"])
    return sorted(commands)


def build_error_registry_contract() -> dict[str, Any]:
    registry: dict[str, Any] = {}
    for code in ERROR_CODES:
        registry[code] = {
            "code": code,
            "category": _error_category(code),
            "description": _error_description(code),
            "commands": _commands_for_error(code),
            "retryable": code in _RETRYABLE_ERROR_CODES,
            "project_modified": code in _PROJECT_MODIFIED_ERROR_CODES,
            "recovery_required": code in _RECOVERY_REQUIRED_ERROR_CODES,
            "exit_code": EXIT_CODE_BY_ERROR_CODE[code],
        }
    return {
        "contract_version": "1.0",
        "protocol_schema_version": PROTOCOL_SCHEMA_VERSION,
        "error_codes": registry,
    }


def build_protocol_contract() -> dict[str, Any]:
    return {
        "contract_version": "1.0",
        "protocol_schema_version": PROTOCOL_SCHEMA_VERSION,
        "capabilities_schema_version": CAPABILITIES_SCHEMA_VERSION,
        "required_envelope_fields": [
            "protocol_schema_version",
            "command",
            "ok",
            "status",
            "error",
            "result",
            "meta",
        ],
        "allowed_statuses": [
            "preview",
            "applied",
            "tested",
            "failed",
            "rolled_back",
            "recovered",
            "noop",
            "refused",
        ],
        "exit_codes": {
            "success": 0,
            "refused_or_usage": 2,
            "tests_failed": 3,
            "security_or_hash_mismatch": 4,
            "internal": 5,
        },
        "error_shape": {
            "required_fields": ["code", "message", "details"],
        },
        "commands": [
            "capabilities",
            "scan",
            "diff",
            "log",
            "rollback",
            "plan",
            "add-docstring",
            "remove-docstring",
            "add-return-type",
            "remove-return-type",
            "add-parameter-type",
            "remove-parameter-type",
            "add-import",
            "remove-import",
            "add-decorator",
            "remove-decorator",
        ],
    }


def build_plan_schema_contract() -> dict[str, Any]:
    return {
        "contract_version": "1.0",
        "plan_schema_version": PLAN_SCHEMA_VERSION,
        "transaction_manifest_schema_version": TRANSACTION_MANIFEST_SCHEMA_VERSION,
        "supported_operations": sorted(SUPPORTED_PLAN_OPERATIONS),
        "required_root_keys": [
            "plan_schema_version",
            "steps",
        ],
        "optional_root_keys": [
            "name",
            "description",
            "client_plan_id",
            "metadata",
        ],
        "required_step_keys": [
            "id",
            "operation",
            "file",
            "arguments",
        ],
        "max_steps": PLAN_MAX_STEPS,
        "manifest_initial_statuses": sorted(TRANSACTION_MANIFEST_INITIAL_STATUSES),
        "manifest_allowed_statuses": sorted(TRANSACTION_MANIFEST_ALLOWED_STATUSES),
        "manifest_transitions": {
            str(key): sorted(value)
            for key, value in TRANSACTION_MANIFEST_TRANSITIONS.items()
        },
    }


def build_sqlite_contract() -> dict[str, Any]:
    connection = sqlite3.connect(":memory:")
    try:
        ensure_schema(connection)
        tables: dict[str, Any] = {}
        for table in [
            "surepython_operations",
            "surepython_plans",
            "surepython_plan_steps",
            "surepython_plan_files",
            "surepython_schema_metadata",
        ]:
            try:
                columns = connection.execute(f"PRAGMA table_info({table})").fetchall()
            except sqlite3.DatabaseError:
                columns = []
            if not columns:
                continue
            tables[table] = {
                "columns": [
                    {
                        "name": row[1],
                        "type": row[2],
                        "notnull": bool(row[3]),
                        "default": row[4],
                        "primary_key": bool(row[5]),
                    }
                    for row in columns
                ]
            }
        return {
            "contract_version": "1.0",
            "schema_version": "1.0",
            "tables": tables,
        }
    finally:
        connection.close()


def _git(command: list[str], *, cwd: Path) -> None:
    subprocess.run(command, cwd=str(cwd), check=True, capture_output=True, text=True)


def _prepare_plan_project(root: Path, source: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    module = root / "service.py"
    module.write_text(source, encoding="utf-8", newline="\r\n")
    tests_dir = root / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_smoke.py").write_text(
        "from service import parse\n\n"
        "def test_smoke():\n"
        "    assert parse('x') == 'x'\n",
        encoding="utf-8",
        newline="\r\n",
    )
    _git(["git", "init"], cwd=root)
    _git(["git", "config", "user.email", "surepython@example.com"], cwd=root)
    _git(["git", "config", "user.name", "SurePython"], cwd=root)
    _git(["git", "add", "."], cwd=root)
    _git(["git", "commit", "--allow-empty", "-m", "baseline"], cwd=root)
    return module


def _preview_vector(root: Path, plan_data: dict[str, Any], *, source: str) -> dict[str, Any]:
    from .plans import preview_plan

    _prepare_plan_project(root, source)
    plan_path = root.parent / f"{root.name}-plan.json"
    plan_path.write_text(json.dumps(plan_data, indent=2, ensure_ascii=False), encoding="utf-8")
    result = preview_plan(plan_path, project_root=root)
    return {
        "name": root.name,
        "plan": plan_data,
        "initial_source": source,
        "expected_preview_hash": result.preview_hash,
        "step_count": result.step_count,
        "file_count": result.file_count,
    }


def build_preview_hash_vectors() -> dict[str, Any]:
    temp_root = Path(tempfile.mkdtemp(prefix="surepython-contract-preview-"))
    vectors: list[dict[str, Any]] = []
    try:
        vectors.append(
            _preview_vector(
                temp_root / "vector-one",
                {
                    "plan_schema_version": "1.0",
                    "steps": [
                        {
                            "id": "add-import",
                            "operation": "add-import",
                            "file": "service.py",
                            "arguments": {"statement": "from pathlib import Path"},
                        },
                        {
                            "id": "add-return-type",
                            "operation": "add-return-type",
                            "file": "service.py",
                            "arguments": {"symbol": "parse", "annotation": "str"},
                        },
                    ],
                },
                source="def parse(source):\n    return source\n",
            )
        )
        vectors.append(
            _preview_vector(
                temp_root / "vector-two",
                {
                    "plan_schema_version": "1.0",
                    "steps": [
                        {
                            "id": "add-docstring",
                            "operation": "add-docstring",
                            "file": "service.py",
                            "arguments": {"symbol": "parse", "docstring": "Parse a source."},
                        }
                    ],
                },
                source="def parse(source):\n    return source\n",
            )
        )
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
    return {
        "contract_version": "1.0",
        "vectors": vectors,
    }


def build_public_contract() -> dict[str, Any]:
    cli_contract = build_cli_contract()
    capabilities_contract = build_capabilities_contract()
    return {
        "contract_version": "1.0",
        "protocol_schema_version": PROTOCOL_SCHEMA_VERSION,
        "capabilities_schema_version": CAPABILITIES_SCHEMA_VERSION,
        "plan_schema_version": PLAN_SCHEMA_VERSION,
        "sources_of_truth": {
            "cli": "contracts/cli_contract_v1.json",
            "capabilities": "contracts/capabilities_v1.json",
            "errors": "contracts/error_registry_v1.json",
            "protocol": "contracts/protocol_envelope_v1.json",
            "plan": "contracts/plan_schema_v1.json",
            "sqlite": "contracts/sqlite_schema_v1.json",
            "preview_hash_vectors": "contracts/fixtures/preview_hash_vectors.json",
            "golden_corpus": "contracts/golden/corpus.json",
            "schemas": [
                "contracts/schemas/protocol-envelope-1.0.schema.json",
                "contracts/schemas/capabilities-1.0.schema.json",
                "contracts/schemas/plan-1.0.schema.json",
                "contracts/schemas/operation-result-1.0.schema.json",
                "contracts/schemas/plan-result-1.0.schema.json",
                "contracts/schemas/error-1.0.schema.json",
            ],
        },
        "commands": sorted(
            [
                action["name"]
                for action in capabilities_contract["operations"]
            ]
            + [command["name"] for command in capabilities_contract.get("commands", [])]
        ),
        "operation_count": len(capabilities_contract["operations"]),
        "command_count": len(capabilities_contract.get("commands", [])),
        "error_code_count": len(ERROR_CODES),
        "supports_json_protocol": True,
        "supports_sqlite_logging": True,
        "supports_transaction_plans": True,
        "cli": cli_contract["tree"],
    }


def contract_snapshots() -> dict[str, tuple[Path, Any]]:
    return {
        "contracts/public_contract_v1.json": (Path("contracts/public_contract_v1.json"), build_public_contract()),
        "contracts/cli_contract_v1.json": (Path("contracts/cli_contract_v1.json"), build_cli_contract()),
        "contracts/capabilities_v1.json": (Path("contracts/capabilities_v1.json"), build_capabilities_contract()),
        "contracts/error_registry_v1.json": (Path("contracts/error_registry_v1.json"), build_error_registry_contract()),
        "contracts/protocol_envelope_v1.json": (Path("contracts/protocol_envelope_v1.json"), build_protocol_contract()),
        "contracts/plan_schema_v1.json": (Path("contracts/plan_schema_v1.json"), build_plan_schema_contract()),
        "contracts/sqlite_schema_v1.json": (Path("contracts/sqlite_schema_v1.json"), build_sqlite_contract()),
        "contracts/fixtures/preview_hash_vectors.json": (
            Path("contracts/fixtures/preview_hash_vectors.json"),
            build_preview_hash_vectors(),
        ),
    }


def write_contract_snapshots(root: Path) -> None:
    for relative_path, payload in contract_snapshots().values():
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_canonical_json(payload) + "\n", encoding="utf-8")


def load_contract_snapshot(name: str, root: Path) -> Any:
    path = root / name
    return json.loads(path.read_text(encoding="utf-8"))


def validate_contract_file(name: str, root: Path, expected: Any) -> None:
    actual = load_contract_snapshot(name, root)
    if actual != expected:
        raise AssertionError(f"Contract snapshot mismatch for {name}")
