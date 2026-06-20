from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FROZEN_REF = "v0.17.0-public-preview"
FROZEN_PATHS = ("contracts", "surepython/contracts")


def _git(*args: str, root: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )


def _format_difference(line: str) -> str:
    parts = line.split("\t")
    status = parts[0]
    if status.startswith("R") and len(parts) >= 3:
        return f"renamed: {parts[1]} -> {parts[2]}"
    if status.startswith("C") and len(parts) >= 3:
        return f"copied: {parts[1]} -> {parts[2]}"
    if status == "A" and len(parts) >= 2:
        return f"added: {parts[1]}"
    if status == "D" and len(parts) >= 2:
        return f"deleted: {parts[1]}"
    if status == "M" and len(parts) >= 2:
        return f"modified: {parts[1]}"
    if len(parts) >= 2:
        return f"{status.lower()}: {parts[-1]}"
    return line


def compare_frozen_contract(root: Path = ROOT, ref: str = FROZEN_REF) -> list[str]:
    completed = _git("diff", "--name-status", "--find-renames=100%", ref, "--", *FROZEN_PATHS, root=root)
    if completed.returncode != 0:
        raise RuntimeError(
            f"git diff failed with exit code {completed.returncode}:\n{completed.stdout}\n{completed.stderr}"
        )
    differences = [
        _format_difference(line.strip())
        for line in completed.stdout.splitlines()
        if line.strip()
    ]
    return differences


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate that the frozen RC1 contract has not changed.")
    parser.add_argument("--ref", default=FROZEN_REF)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    differences = compare_frozen_contract(ref=args.ref)
    if differences:
        print("FROZEN_CONTRACT_CHANGED", file=sys.stderr)
        for difference in differences:
            print(difference, file=sys.stderr)
        return 1
    print(f"Frozen contract matches {args.ref}.")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI wrapper
    raise SystemExit(main())
