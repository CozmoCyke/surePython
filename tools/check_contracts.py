from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from surepython.public_contract import contract_snapshots


DOC_FILES = [
    "README.md",
    "AGENTS.md",
    "docs/TUTORIAL_FR.md",
    "docs/CODEX_INTEGRATION.md",
    "docs/AGENTS_TEMPLATE.md",
    "docs/PROTOCOL_JSON.md",
    "docs/PLAN_SCHEMA_V1.md",
    "docs/TRANSACTIONAL_PLANS.md",
    "docs/SELF_HOSTING.md",
    "docs/WINDOWS_TROUBLESHOOTING.md",
    "docs/COMPATIBILITY_POLICY.md",
    "docs/DEPRECATION_POLICY.md",
    "docs/VERSIONING_POLICY.md",
    "docs/PUBLIC_API.md",
    "docs/ERROR_CODES.md",
]

SCHEMA_FILES = [
    "contracts/schemas/protocol-envelope-1.0.schema.json",
    "contracts/schemas/capabilities-1.0.schema.json",
    "contracts/schemas/plan-1.0.schema.json",
    "contracts/schemas/operation-result-1.0.schema.json",
    "contracts/schemas/plan-result-1.0.schema.json",
    "contracts/schemas/error-1.0.schema.json",
]

GOLDEN_FILES = [
    "contracts/golden/corpus.json",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _json_text(data: object) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_json_blocks(text: str) -> list[str]:
    pattern = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
    return [match.group(1) for match in pattern.finditer(text)]


def _validate_docs(root: Path) -> list[str]:
    errors: list[str] = []
    for relative in DOC_FILES:
        path = root / relative
        if not path.exists():
            errors.append(f"Missing documented contract file: {relative}")
            continue
        text = path.read_text(encoding="utf-8")
        for index, block in enumerate(_extract_json_blocks(text), start=1):
            try:
                json.loads(block)
            except json.JSONDecodeError as exc:
                errors.append(f"Invalid JSON block in {relative} #{index}: {exc}")
    return errors


def _validate_schema_files(root: Path) -> list[str]:
    errors: list[str] = []
    for relative in SCHEMA_FILES:
        path = root / relative
        if not path.exists():
            errors.append(f"Missing schema file: {relative}")
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"Invalid schema JSON in {relative}: {exc}")
    return errors


def _validate_golden_files(root: Path) -> list[str]:
    errors: list[str] = []
    for relative in GOLDEN_FILES:
        path = root / relative
        if not path.exists():
            errors.append(f"Missing golden corpus file: {relative}")
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"Invalid golden JSON in {relative}: {exc}")
    return errors


def _validate_snapshots(root: Path, *, write: bool) -> list[str]:
    errors: list[str] = []
    for relative, (_path_obj, expected) in contract_snapshots().items():
        target = root / relative
        if write:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(_json_text(expected), encoding="utf-8")
            continue
        if not target.exists():
            errors.append(f"Missing snapshot: {relative}")
            continue
        actual = _read_json(target)
        if actual != expected:
            errors.append(f"Snapshot mismatch: {relative}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the public SurePython contract snapshots.")
    parser.add_argument("--write", action="store_true", help="Regenerate the contract snapshots from code.")
    args = parser.parse_args(argv)

    root = _repo_root()
    errors = []
    errors.extend(_validate_snapshots(root, write=args.write))
    if not args.write:
        errors.extend(_validate_schema_files(root))
    if not args.write:
        errors.extend(_validate_golden_files(root))
    if not args.write:
        errors.extend(_validate_docs(root))

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print("Contract snapshots are in sync.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
