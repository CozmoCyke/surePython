from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .codemods import add_docstring
from .datasette_log import insert_record, read_last_operation
from .git_tools import GitError, find_git_root, git_diff
from .scanner import scan_project


def _print_error(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)


def _cmd_scan(path: Path) -> int:
    records = scan_project(path)
    print("file\ttype\tqualified_name\tline_start\tline_end\thas_docstring")
    for record in records:
        print(
            "\t".join(
                [
                    record.file,
                    record.type,
                    record.qualified_name,
                    str(record.line_start),
                    str(record.line_end),
                    "yes" if record.has_docstring else "no",
                ]
            )
        )
    return 0


def _cmd_add_docstring(file_path: Path, function: str, test: bool, test_command: str | None) -> int:
    try:
        result = add_docstring(
            file_path,
            function,
            project_root=file_path.parent,
            run_tests=test,
            test_command=test_command,
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

    add_parser = subparsers.add_parser("add-docstring", help="Add a skeleton docstring")
    add_parser.add_argument("file_path", type=Path)
    add_parser.add_argument("--function", required=True)
    add_parser.add_argument("--test", action="store_true")
    add_parser.add_argument("--test-command")

    subparsers.add_parser("diff", help="Show git diff")

    log_parser = subparsers.add_parser("log", help="Log the last operation to SQLite")
    log_parser.add_argument("--db", type=Path, required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "scan":
        return _cmd_scan(args.path)
    if args.command == "add-docstring":
        return _cmd_add_docstring(args.file_path, args.function, args.test, args.test_command)
    if args.command == "diff":
        return _cmd_diff()
    if args.command == "log":
        return _cmd_log(args.db)
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

