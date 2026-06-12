from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path
import sys

from .codemods import add_docstring
from .datasette_log import insert_record, read_last_operation
from .git_tools import GitError, find_git_root, git_diff
from .scanner import scan_project


SCAN_FIELDS = [
    "file",
    "type",
    "name",
    "qualified_name",
    "line_start",
    "line_end",
    "has_docstring",
]


def _print_error(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)


def _serialize_scan_records(records, output_format: str) -> str:
    payload = [
        {
            "file": record.file,
            "type": record.type,
            "name": record.name,
            "qualified_name": record.qualified_name,
            "line_start": record.line_start,
            "line_end": record.line_end,
            "has_docstring": record.has_docstring,
        }
        for record in records
    ]

    if output_format == "text":
        lines = ["\t".join(SCAN_FIELDS)]
        for item in payload:
            lines.append(
                "\t".join(
                    [
                        item["file"],
                        item["type"],
                        item["name"],
                        item["qualified_name"],
                        str(item["line_start"]),
                        str(item["line_end"]),
                        "yes" if item["has_docstring"] else "no",
                    ]
                )
            )
        return "\n".join(lines)

    if output_format == "json":
        return json.dumps(payload, indent=2, ensure_ascii=False)

    if output_format == "csv":
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=SCAN_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(payload)
        return buffer.getvalue().rstrip("\r\n")

    raise ValueError(f"Unsupported scan format: {output_format}")


def _cmd_scan(path: Path, output_format: str) -> int:
    records = scan_project(path)
    print(_serialize_scan_records(records, output_format))
    return 0


def _cmd_add_docstring(
    file_path: Path,
    function: str,
    test: bool,
    test_command: str | None,
    dry_run: bool,
) -> int:
    try:
        result = add_docstring(
            file_path,
            function,
            project_root=file_path.parent,
            run_tests=test,
            test_command=test_command,
            dry_run=dry_run,
        )
    except GitError as exc:
        _print_error(str(exc))
        return 1

    print("SurePython v0.1")
    print(f"Project:\n  {result.project_root}")
    print("Operation:\n  add-docstring")
    print(f"Target:\n  {result.file_path.name}::{result.symbol}")
    print("Safety:")
    print("  Git repository: OK")
    print("  Git clean: OK")
    print("  File inside project: OK")
    print("  LibCST parse: OK")
    if dry_run:
        print("Mode:")
        print("  Dry run; no files changed.")
        print("Preview diff:")
        if result.preview_diff_text:
            print(result.preview_diff_text.rstrip())
    else:
        print("Applied:")
        print("  Added skeleton docstring.")
        print("Diff:")
        if result.git_stat.strip():
            print(result.git_stat.rstrip())
        if result.git_diff_text.strip():
            print(result.git_diff_text.rstrip())
    if result.pytest_command:
        print("Test:")
        print(f"  {result.pytest_command} -> exit {result.pytest_exit_code}")
    print("Next:")
    print("  Run:")
    print("    surepython diff")
    print("    surepython log --db <path>")
    return 0


def _cmd_diff() -> int:
    cwd = Path.cwd()
    root = find_git_root(cwd)
    if root is None:
        _print_error("Not a git repository")
        return 1
    stat, diff_text = git_diff(root)
    if stat.strip():
        print(stat.rstrip())
    if diff_text.strip():
        print(diff_text.rstrip())
    return 0


def _cmd_log(db: Path) -> int:
    try:
        record = read_last_operation()
        insert_record(db, record)
    except FileNotFoundError as exc:
        _print_error(str(exc))
        return 1

    print(f"Logged operation to {db}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="surepython", description="SurePython v0.1")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Scan Python symbols")
    scan_parser.add_argument("path", type=Path)
    scan_parser.add_argument("--format", choices=["text", "json", "csv"], default="text")

    add_parser = subparsers.add_parser("add-docstring", help="Add a skeleton docstring")
    add_parser.add_argument("file_path", type=Path)
    add_parser.add_argument("--function", required=True)
    add_parser.add_argument("--test", action="store_true")
    add_parser.add_argument("--test-command")
    add_parser.add_argument("--dry-run", action="store_true")

    subparsers.add_parser("diff", help="Show git diff")

    log_parser = subparsers.add_parser("log", help="Log the last operation to SQLite")
    log_parser.add_argument("--db", type=Path, required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "scan":
        return _cmd_scan(args.path, args.format)
    if args.command == "add-docstring":
        return _cmd_add_docstring(args.file_path, args.function, args.test, args.test_command, args.dry_run)
    if args.command == "diff":
        return _cmd_diff()
    if args.command == "log":
        return _cmd_log(args.db)
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
