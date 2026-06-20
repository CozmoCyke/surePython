from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

from surepython.public_contract import (
    build_capabilities_contract,
    build_cli_contract,
    build_error_registry_contract,
    build_plan_schema_contract,
    build_preview_hash_vectors,
    build_protocol_contract,
    build_public_contract,
    build_sqlite_contract,
)
from surepython.plans import preview_plan
from surepython.datasette_log import ensure_schema


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"


def _read_json(relative: str) -> object:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _run_surepython(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "surepython", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def _extract_json_blocks(text: str) -> list[str]:
    pattern = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
    return [match.group(1) for match in pattern.finditer(text)]


def _build_preview_hash(project_root: Path, plan_data: dict[str, object], source: str) -> str:
    project_root.mkdir(parents=True, exist_ok=True)
    module = project_root / "service.py"
    # Match the contract snapshot generator exactly so hashes stay stable across OSes.
    module.write_text(source, encoding="utf-8", newline="\r\n")
    tests_dir = project_root / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_smoke.py").write_text(
        "from service import parse\n\n"
        "def test_smoke():\n"
        "    assert parse('x') == 'x'\n",
        encoding="utf-8",
        newline="\r\n",
    )
    subprocess.run(["git", "init"], cwd=str(project_root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "surepython@example.com"], cwd=str(project_root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "SurePython"], cwd=str(project_root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=str(project_root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "baseline"], cwd=str(project_root), check=True, capture_output=True, text=True)
    plan_path = project_root.parent / f"{project_root.name}-plan.json"
    plan_path.write_text(json.dumps(plan_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return preview_plan(plan_path, project_root=project_root).preview_hash


def test_public_contract_snapshots_match_current_code() -> None:
    assert _read_json("contracts/public_contract_v1.json") == build_public_contract()
    assert _read_json("contracts/cli_contract_v1.json") == build_cli_contract()
    assert _read_json("contracts/capabilities_v1.json") == build_capabilities_contract()
    assert _read_json("contracts/error_registry_v1.json") == build_error_registry_contract()
    assert _read_json("contracts/protocol_envelope_v1.json") == build_protocol_contract()
    assert _read_json("contracts/plan_schema_v1.json") == build_plan_schema_contract()
    assert _read_json("contracts/sqlite_schema_v1.json") == build_sqlite_contract()
    assert _read_json("contracts/fixtures/preview_hash_vectors.json") == build_preview_hash_vectors()


def test_check_contracts_script_passes() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/check_contracts.py"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Contract snapshots are in sync." in completed.stdout


def test_normative_docs_contain_parseable_json_blocks() -> None:
    docs = [
        "README.md",
        "AGENTS.md",
        "docs/PROTOCOL_JSON.md",
        "docs/PLAN_SCHEMA_V1.md",
        "docs/COMPATIBILITY_POLICY.md",
        "docs/DEPRECATION_POLICY.md",
        "docs/VERSIONING_POLICY.md",
        "docs/PUBLIC_API.md",
        "docs/ERROR_CODES.md",
    ]
    for relative in docs:
        text = (ROOT / relative).read_text(encoding="utf-8")
        for block in _extract_json_blocks(text):
            json.loads(block)


def test_schema_and_golden_corpus_files_are_parseable() -> None:
    schema_files = [
        "contracts/schemas/protocol-envelope-1.0.schema.json",
        "contracts/schemas/capabilities-1.0.schema.json",
        "contracts/schemas/plan-1.0.schema.json",
        "contracts/schemas/operation-result-1.0.schema.json",
        "contracts/schemas/plan-result-1.0.schema.json",
        "contracts/schemas/error-1.0.schema.json",
        "contracts/golden/corpus.json",
    ]
    for relative in schema_files:
        json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_help_output_lists_only_public_commands() -> None:
    completed = _run_surepython("--help")
    assert completed.returncode == 0
    assert "capabilities" in completed.stdout
    assert "scan" in completed.stdout
    assert "plan" in completed.stdout
    assert "remove-decorator" in completed.stdout
    assert "transaction_lock" not in completed.stdout

    plan_help = _run_surepython("plan", "--help")
    assert plan_help.returncode == 0
    assert "preview" in plan_help.stdout
    assert "apply" in plan_help.stdout
    assert "rollback" in plan_help.stdout
    assert "recover" in plan_help.stdout

    rollback_help = _run_surepython("rollback", "--help")
    assert rollback_help.returncode == 0
    assert "--last" in rollback_help.stdout
    assert "--id" in rollback_help.stdout


def test_sqlite_schema_includes_additive_metadata_table(tmp_path: Path) -> None:
    db_path = tmp_path / "surepython.db"
    connection = sqlite3.connect(str(db_path))
    try:
        ensure_schema(connection)
        rows = connection.execute("PRAGMA table_info(surepython_schema_metadata)").fetchall()
        assert [row[1] for row in rows] == [
            "schema_version",
            "created_by_version",
            "last_migrated_by_version",
        ]
        metadata = connection.execute(
            "SELECT schema_version, created_by_version, last_migrated_by_version FROM surepython_schema_metadata"
        ).fetchone()
        assert metadata == ("1.0", "0.17.0", "0.17.0")
    finally:
        connection.close()


def test_preview_hash_vectors_match_preview_plan(tmp_path: Path) -> None:
    vectors = _read_json("contracts/fixtures/preview_hash_vectors.json")
    for vector in vectors["vectors"]:
        project_root = tmp_path / vector["name"]
        expected_hash = _build_preview_hash(project_root, vector["plan"], vector["initial_source"])
        assert expected_hash == vector["expected_preview_hash"]
