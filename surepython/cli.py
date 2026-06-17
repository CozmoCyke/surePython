from __future__ import annotations

import dataclasses
import argparse
import csv
import io
import json
from pathlib import Path
import sys

from .capabilities import serialize_capabilities
from .codemods import (
    add_decorator,
    add_docstring,
    add_import,
    add_parameter_type,
    add_return_type,
    remove_import,
    remove_docstring,
    remove_parameter_type,
    remove_return_type,
    remove_decorator,
)
from .datasette_log import insert_record, read_last_operation
from .git_tools import GitError, find_git_root, git_diff
from .plans import (
    _ensure_no_recovery_required,
    apply_plan,
    preview_plan,
    recover_plan,
    rollback_plan as rollback_transactional_plan,
)
from .transaction_lock import acquire_project_mutation_lock
from .protocol import (
    EXIT_INTERNAL,
    build_protocol_response,
    dump_json,
    ProtocolError,
)
from .rollback import rollback_by_id, rollback_last
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


def _error_status_for_code(code: str) -> str:
    if code == "TESTS_FAILED":
        return "failed"
    if code in {"DATABASE_ERROR", "INTERNAL_ERROR"}:
        return "failed"
    return "refused"


def _print_json_response(payload: dict[str, object]) -> None:
    print(dump_json(payload))


def _build_error_payload(exc: ProtocolError) -> dict[str, object]:
    return exc.to_payload()


def _mutation_root_for(path: Path) -> Path:
    git_root = find_git_root(path)
    return git_root if git_root is not None else path.resolve()


def _build_operation_result_payload(command: str, result, output_format: str, dry_run: bool) -> dict[str, object]:
    if command == "rollback":
        target = {"file": result.file_path.name, "symbol": result.symbol}
        if result.target_kind is not None:
            target["kind"] = result.target_kind
        if result.parameter is not None:
            target["parameter"] = result.parameter
        if result.parameter_kind is not None:
            target["parameter_kind"] = result.parameter_kind
        if result.parameter_annotation is not None:
            target["parameter_annotation"] = result.parameter_annotation
        if result.return_annotation is not None:
            target["return_annotation"] = result.return_annotation
        if result.expected_docstring_text is not None:
            target["expected_docstring_text"] = result.expected_docstring_text
        if result.removed_docstring_text is not None:
            target["removed_docstring_text"] = result.removed_docstring_text
        if result.docstring_replacement_statement is not None:
            target["docstring_replacement_statement"] = result.docstring_replacement_statement
        if result.docstring_target_kind is not None:
            target["docstring_target_kind"] = result.docstring_target_kind
        if result.expected_import_statement is not None:
            target["kind"] = "module_import"
            target["expected_import_statement"] = result.expected_import_statement
        if result.removed_import_statement is not None:
            target["removed_import_statement"] = result.removed_import_statement
        if result.import_binding is not None:
            target["import_binding"] = result.import_binding
        if result.import_match_count is not None:
            target["import_match_count"] = result.import_match_count
        payload = {
            "operation": "rollback",
            "selector": {
                "type": result.selector_type,
                "value": result.selector_value,
            },
            "source_operation": result.source_operation,
            "source_operation_id": result.source_operation_id,
            "operation_id": result.rollback_operation_id,
            "rollback_operation_id": result.rollback_operation_id,
            "target": target,
            "written": result.written,
            "logged": result.logged,
            "bytes_equal": result.bytes_equal,
            "byte_exact": result.byte_exact,
            "before_sha256": result.before_sha256,
            "restored_sha256": result.after_sha256,
            "diff": result.preview_diff_text,
        }
        if result.return_annotation is not None:
            payload["return_annotation"] = result.return_annotation
        if result.parameter_annotation is not None:
            payload["parameter_annotation"] = result.parameter_annotation
        if result.expected_import_statement is not None:
            payload["expected_import_statement"] = result.expected_import_statement
        if result.removed_import_statement is not None:
            payload["removed_import_statement"] = result.removed_import_statement
        if result.import_binding is not None:
            payload["import_binding"] = result.import_binding
        if result.import_match_count is not None:
            payload["import_match_count"] = result.import_match_count
        if output_format == "json":
            return payload
        return payload

    payload = {
        "operation": command,
        "operation_id": result.operation_id,
        "target": {"file": result.file_path.name, "symbol": result.symbol},
        "written": not dry_run,
        "logged": result.logged,
        "rollback_available": result.rollback_available,
        "diff": result.preview_diff_text if dry_run else result.git_diff_text,
        "before_sha256": result.before_sha256,
        "after_sha256": result.after_sha256,
    }
    if command == "add-return-type":
        payload["annotation"] = result.annotation
    if command == "remove-docstring":
        payload["expected_docstring_text"] = result.expected_docstring_text
        payload["removed_docstring_text"] = result.removed_docstring_text
        payload["removed_docstring_source"] = result.removed_docstring_source
        payload["docstring_replacement_statement"] = result.docstring_replacement_statement
        payload["target"] = {
            "file": result.file_path.name,
            "symbol": result.symbol,
            "kind": result.target_kind,
        }
    if command == "remove-return-type":
        payload["expected_annotation"] = result.expected_annotation
        payload["annotation"] = result.annotation
    if command == "remove-parameter-type":
        payload["expected_annotation"] = result.expected_annotation
        payload["removed_annotation"] = result.removed_annotation
        payload["parameter"] = result.parameter
        payload["parameter_kind"] = result.parameter_kind
        payload["target"] = {
            "file": result.file_path.name,
            "symbol": result.symbol,
            "kind": result.target_kind,
            "parameter": result.parameter,
            "parameter_kind": result.parameter_kind,
        }
    if command == "add-parameter-type":
        payload["parameter"] = result.parameter
        payload["annotation"] = result.annotation
        payload["target"] = {
            "file": result.file_path.name,
            "symbol": result.symbol,
            "parameter": result.parameter,
        }
    if command == "add-import":
        payload["binding"] = result.binding
        payload["statement"] = result.statement
        payload["target"] = {
            "file": result.file_path.name,
            "binding": result.binding,
        }
    if command == "remove-import":
        payload["expected_import_statement"] = result.expected_import_statement
        payload["removed_import_statement"] = result.removed_import_statement
        payload["import_binding"] = result.import_binding
        payload["binding"] = result.import_binding
        payload["match_count"] = result.import_match_count
        payload["target"] = {
            "file": result.file_path.name,
            "kind": result.target_kind,
        }
    if command == "add-decorator":
        payload["decorator"] = result.decorator
        payload["position"] = result.position
        payload["target"] = {
            "file": result.file_path.name,
            "symbol": result.symbol,
            "kind": result.target_kind,
        }
    if command == "remove-decorator":
        payload["expected_decorator"] = result.expected_decorator
        payload["expected_position"] = result.expected_position
        payload["removed_decorator"] = result.removed_decorator
        payload["removed_position"] = result.removed_position
        payload["target"] = {
            "file": result.file_path.name,
            "symbol": result.symbol,
            "kind": result.target_kind,
        }
    if result.pytest_command is not None:
        payload["tests"] = {
            "command": result.pytest_command,
            "exit_code": result.pytest_exit_code,
            "status": result.pytest_status,
        }
    else:
        payload["tests"] = None
    return payload


def _build_plan_result_payload(result) -> dict[str, object]:
    payload = dataclasses.asdict(result)
    if payload.get("pytest_command") is not None:
        payload["tests"] = {
            "command": payload.pop("pytest_command"),
            "exit_code": payload.pop("pytest_exit_code"),
            "status": payload.pop("pytest_status"),
        }
    else:
        payload["tests"] = None
        payload.pop("pytest_command", None)
        payload.pop("pytest_exit_code", None)
        payload.pop("pytest_status", None)
    return payload


def _emit_error(command: str, exc: ProtocolError, output_format: str, *, meta: dict[str, object] | None = None) -> int:
    if output_format == "json":
        _print_json_response(
            build_protocol_response(
                command=command,
                ok=False,
                status=_error_status_for_code(exc.code),
                error=_build_error_payload(exc),
                result=None,
                meta=meta or {},
            )
        )
    else:
        _print_error(str(exc))
    return exc.exit_code


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


def _cmd_capabilities(output_format: str) -> int:
    try:
        print(serialize_capabilities(output_format))
    except ValueError as exc:
        _print_error(str(exc))
        return 1
    return 0


def _cmd_add_docstring(
    file_path: Path,
    function: str,
    test: bool,
    test_command: str | None,
    dry_run: bool,
    db: Path | None,
    output_format: str,
) -> int:
    try:
        with acquire_project_mutation_lock(_mutation_root_for(file_path.parent), "add-docstring"):
            _ensure_no_recovery_required(_mutation_root_for(file_path.parent))
            result = add_docstring(
                file_path,
                function,
                project_root=file_path.parent,
                db_path=db,
                run_tests=test,
                test_command=test_command,
                dry_run=dry_run,
            )
    except GitError as exc:
        return _emit_error("add-docstring", exc, output_format, meta={"dry_run": dry_run, "format": output_format})

    if output_format == "json":
        _print_json_response(
            build_protocol_response(
                command="add-docstring",
                ok=result.exit_code == 0,
                status="preview" if dry_run else result.status,
                error=None
                if result.exit_code == 0
                else {
                    "code": "TESTS_FAILED",
                    "message": "pytest exited with a non-zero status",
                    "details": {"exit_code": result.pytest_exit_code},
                },
                result=_build_operation_result_payload("add-docstring", result, output_format, dry_run),
                meta={"dry_run": dry_run, "format": "json"},
            )
        )
        return result.exit_code

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
        if result.pytest_status:
            print(f"  Status: {result.pytest_status}")
    if result.logged:
        print("Log:")
        print(f"  SQLite: {result.db_path}")
    print("Next:")
    print("  Run:")
    print("    surepython diff")
    print("    surepython log --db <path>")
    return result.exit_code


def _cmd_remove_docstring(
    file_path: Path,
    symbol: str,
    expect_docstring: str,
    test: bool,
    test_command: str | None,
    dry_run: bool,
    db: Path | None,
    output_format: str,
) -> int:
    try:
        with acquire_project_mutation_lock(_mutation_root_for(file_path.parent), "remove-docstring"):
            _ensure_no_recovery_required(_mutation_root_for(file_path.parent))
            result = remove_docstring(
                file_path,
                symbol,
                expect_docstring,
                project_root=file_path.parent,
                db_path=db,
                run_tests=test,
                test_command=test_command,
                dry_run=dry_run,
            )
    except GitError as exc:
        return _emit_error(
            "remove-docstring",
            exc,
            output_format,
            meta={"dry_run": dry_run, "format": output_format},
        )

    if output_format == "json":
        _print_json_response(
            build_protocol_response(
                command="remove-docstring",
                ok=result.exit_code == 0,
                status="preview" if dry_run else result.status,
                error=None
                if result.exit_code == 0
                else {
                    "code": "TESTS_FAILED",
                    "message": "pytest exited with a non-zero status",
                    "details": {"exit_code": result.pytest_exit_code},
                },
                result=_build_operation_result_payload("remove-docstring", result, output_format, dry_run),
                meta={"dry_run": dry_run, "format": "json"},
            )
        )
        return result.exit_code

    print("SurePython v0.1")
    print(f"Project:\n  {result.project_root}")
    print("Operation:\n  remove-docstring")
    print(f"Target:\n  {result.file_path.name}::{result.symbol}")
    print(f"Expected docstring:\n  {result.expected_docstring_text}")
    print(f"Removed docstring:\n  {result.removed_docstring_text}")
    if result.docstring_replacement_statement is not None:
        print(f"Replacement:\n  {result.docstring_replacement_statement}")
    print(f"Target kind:\n  {result.target_kind}")
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
        print("  Removed docstring.")
        print("Diff:")
        if result.git_stat.strip():
            print(result.git_stat.rstrip())
        if result.git_diff_text.strip():
            print(result.git_diff_text.rstrip())
    if result.pytest_command:
        print("Test:")
        print(f"  {result.pytest_command} -> exit {result.pytest_exit_code}")
        if result.pytest_status:
            print(f"  Status: {result.pytest_status}")
    if result.logged:
        print("Log:")
        print(f"  SQLite: {result.db_path}")
    print("Next:")
    print("  Run:")
    print("    surepython diff")
    print("    surepython log --db <path>")
    return result.exit_code


def _cmd_add_import(
    file_path: Path,
    statement: str,
    test: bool,
    test_command: str | None,
    dry_run: bool,
    db: Path | None,
    output_format: str,
) -> int:
    try:
        with acquire_project_mutation_lock(_mutation_root_for(file_path.parent), "add-import"):
            _ensure_no_recovery_required(_mutation_root_for(file_path.parent))
            result = add_import(
                file_path,
                statement,
                project_root=file_path.parent,
                db_path=db,
                run_tests=test,
                test_command=test_command,
                dry_run=dry_run,
            )
    except GitError as exc:
        return _emit_error("add-import", exc, output_format, meta={"dry_run": dry_run, "format": output_format})

    if output_format == "json":
        _print_json_response(
            build_protocol_response(
                command="add-import",
                ok=result.exit_code == 0,
                status="preview" if dry_run else result.status,
                error=None
                if result.exit_code == 0
                else {
                    "code": "TESTS_FAILED",
                    "message": "pytest exited with a non-zero status",
                    "details": {"exit_code": result.pytest_exit_code},
                },
                result=_build_operation_result_payload("add-import", result, output_format, dry_run),
                meta={"dry_run": dry_run, "format": "json"},
            )
        )
        return result.exit_code

    print("SurePython v0.1")
    print(f"Project:\n  {result.project_root}")
    print("Operation:\n  add-import")
    print(f"Target:\n  {result.file_path.name}::{result.binding}")
    print(f"Statement:\n  {result.statement}")
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
        print("  Added import statement.")
        print("Diff:")
        if result.git_stat.strip():
            print(result.git_stat.rstrip())
        if result.git_diff_text.strip():
            print(result.git_diff_text.rstrip())
    if result.pytest_command:
        print("Test:")
        print(f"  {result.pytest_command} -> exit {result.pytest_exit_code}")
        if result.pytest_status:
            print(f"  Status: {result.pytest_status}")
    if result.logged:
        print("Log:")
        print(f"  SQLite: {result.db_path}")
    print("Next:")
    print("  Run:")
    print("    surepython diff")
    print("    surepython log --db <path>")
    return result.exit_code


def _cmd_remove_import(
    file_path: Path,
    expect_statement: str,
    test: bool,
    test_command: str | None,
    dry_run: bool,
    db: Path | None,
    output_format: str,
) -> int:
    try:
        with acquire_project_mutation_lock(_mutation_root_for(file_path.parent), "remove-import"):
            _ensure_no_recovery_required(_mutation_root_for(file_path.parent))
            result = remove_import(
                file_path,
                expect_statement,
                project_root=file_path.parent,
                db_path=db,
                run_tests=test,
                test_command=test_command,
                dry_run=dry_run,
            )
    except GitError as exc:
        return _emit_error("remove-import", exc, output_format, meta={"dry_run": dry_run, "format": output_format})

    if output_format == "json":
        _print_json_response(
            build_protocol_response(
                command="remove-import",
                ok=result.exit_code == 0,
                status="preview" if dry_run else result.status,
                error=None
                if result.exit_code == 0
                else {
                    "code": "TESTS_FAILED",
                    "message": "pytest exited with a non-zero status",
                    "details": {"exit_code": result.pytest_exit_code},
                },
                result=_build_operation_result_payload("remove-import", result, output_format, dry_run),
                meta={"dry_run": dry_run, "format": "json"},
            )
        )
        return result.exit_code

    print("SurePython v0.1")
    print(f"Project:\n  {result.project_root}")
    print("Operation:\n  remove-import")
    print(f"Target:\n  {result.file_path.name}::module_import")
    print(f"Expected statement:\n  {result.expected_import_statement}")
    print(f"Removed statement:\n  {result.removed_import_statement}")
    print(f"Binding:\n  {result.import_binding}")
    print(f"Match count:\n  {result.import_match_count}")
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
        print("  Removed import statement.")
        print("Diff:")
        if result.git_stat.strip():
            print(result.git_stat.rstrip())
        if result.git_diff_text.strip():
            print(result.git_diff_text.rstrip())
    if result.pytest_command:
        print("Test:")
        print(f"  {result.pytest_command} -> exit {result.pytest_exit_code}")
        if result.pytest_status:
            print(f"  Status: {result.pytest_status}")
    if result.logged:
        print("Log:")
        print(f"  SQLite: {result.db_path}")
    print("Next:")
    print("  Run:")
    print("    surepython diff")
    print("    surepython log --db <path>")
    return result.exit_code


def _cmd_add_decorator(
    file_path: Path,
    symbol: str | None,
    decorator: str | None,
    position: str | None,
    test: bool,
    test_command: str | None,
    dry_run: bool,
    db: Path | None,
    output_format: str,
) -> int:
    if symbol is None or not symbol.strip():
        exc = GitError("Symbol is required", code="TARGET_NOT_FOUND")
        return _emit_error("add-decorator", exc, output_format, meta={"dry_run": dry_run, "format": output_format})
    if decorator is None or not decorator.strip():
        exc = GitError("Decorator expression is required", code="DECORATOR_REQUIRED")
        return _emit_error("add-decorator", exc, output_format, meta={"dry_run": dry_run, "format": output_format})
    if position is None or not position.strip():
        exc = GitError("Decorator position is required", code="DECORATOR_POSITION_REQUIRED")
        return _emit_error("add-decorator", exc, output_format, meta={"dry_run": dry_run, "format": output_format})
    try:
        with acquire_project_mutation_lock(_mutation_root_for(file_path.parent), "add-decorator"):
            _ensure_no_recovery_required(_mutation_root_for(file_path.parent))
            result = add_decorator(
                file_path,
                symbol,
                decorator,
                position,
                project_root=file_path.parent,
                db_path=db,
                run_tests=test,
                test_command=test_command,
                dry_run=dry_run,
            )
    except GitError as exc:
        return _emit_error("add-decorator", exc, output_format, meta={"dry_run": dry_run, "format": output_format})

    if output_format == "json":
        _print_json_response(
            build_protocol_response(
                command="add-decorator",
                ok=result.exit_code == 0,
                status="preview" if dry_run else result.status,
                error=None
                if result.exit_code == 0
                else {
                    "code": "TESTS_FAILED",
                    "message": "pytest exited with a non-zero status",
                    "details": {"exit_code": result.pytest_exit_code},
                },
                result=_build_operation_result_payload("add-decorator", result, output_format, dry_run),
                meta={"dry_run": dry_run, "format": "json"},
            )
        )
        return result.exit_code

    print("SurePython v0.1")
    print(f"Project:\n  {result.project_root}")
    print("Operation:\n  add-decorator")
    print(f"Target:\n  {result.file_path.name}::{result.symbol}")
    print(f"Kind:\n  {result.target_kind}")
    print(f"Decorator:\n  {result.decorator}")
    print(f"Position:\n  {result.position}")
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
        print("  Added decorator.")
        print("Diff:")
        if result.git_stat.strip():
            print(result.git_stat.rstrip())
        if result.git_diff_text.strip():
            print(result.git_diff_text.rstrip())
    if result.pytest_command:
        print("Test:")
        print(f"  {result.pytest_command} -> exit {result.pytest_exit_code}")
        if result.pytest_status:
            print(f"  Status: {result.pytest_status}")
    if result.logged:
        print("Log:")
        print(f"  SQLite: {result.db_path}")
    print("Next:")
    print("  Run:")
    print("    surepython diff")
    print("    surepython log --db <path>")
    return result.exit_code


def _cmd_remove_decorator(
    file_path: Path,
    symbol: str | None,
    expected_decorator: str | None,
    expected_position: str | None,
    test: bool,
    test_command: str | None,
    dry_run: bool,
    db: Path | None,
    output_format: str,
) -> int:
    if symbol is None or not symbol.strip():
        exc = GitError("Symbol is required", code="TARGET_NOT_FOUND")
        return _emit_error("remove-decorator", exc, output_format, meta={"dry_run": dry_run, "format": output_format})
    if expected_decorator is None or not expected_decorator.strip():
        exc = GitError("Decorator expression is required", code="DECORATOR_REQUIRED")
        return _emit_error("remove-decorator", exc, output_format, meta={"dry_run": dry_run, "format": output_format})
    if expected_position is None or not expected_position.strip():
        exc = GitError("Decorator position is required", code="DECORATOR_POSITION_REQUIRED")
        return _emit_error("remove-decorator", exc, output_format, meta={"dry_run": dry_run, "format": output_format})
    try:
        with acquire_project_mutation_lock(_mutation_root_for(file_path.parent), "remove-decorator"):
            _ensure_no_recovery_required(_mutation_root_for(file_path.parent))
            result = remove_decorator(
                file_path,
                symbol,
                expected_decorator,
                expected_position,
                project_root=file_path.parent,
                db_path=db,
                run_tests=test,
                test_command=test_command,
                dry_run=dry_run,
            )
    except GitError as exc:
        return _emit_error("remove-decorator", exc, output_format, meta={"dry_run": dry_run, "format": output_format})

    if output_format == "json":
        _print_json_response(
            build_protocol_response(
                command="remove-decorator",
                ok=result.exit_code == 0,
                status="preview" if dry_run else result.status,
                error=None
                if result.exit_code == 0
                else {
                    "code": "TESTS_FAILED",
                    "message": "pytest exited with a non-zero status",
                    "details": {"exit_code": result.pytest_exit_code},
                },
                result=_build_operation_result_payload("remove-decorator", result, output_format, dry_run),
                meta={"dry_run": dry_run, "format": "json"},
            )
        )
        return result.exit_code

    print("SurePython v0.1")
    print(f"Project:\n  {result.project_root}")
    print("Operation:\n  remove-decorator")
    print(f"Target:\n  {result.file_path.name}::{result.symbol}")
    print(f"Kind:\n  {result.target_kind}")
    print(f"Expected decorator:\n  {result.expected_decorator}")
    print(f"Expected position:\n  {result.expected_position}")
    print(f"Removed decorator:\n  {result.removed_decorator}")
    print(f"Removed position:\n  {result.removed_position}")
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
        print("  Removed decorator.")
        print("Diff:")
        if result.git_stat.strip():
            print(result.git_stat.rstrip())
        if result.git_diff_text.strip():
            print(result.git_diff_text.rstrip())
    if result.pytest_command:
        print("Test:")
        print(f"  {result.pytest_command} -> exit {result.pytest_exit_code}")
        if result.pytest_status:
            print(f"  Status: {result.pytest_status}")
    if result.logged:
        print("Log:")
        print(f"  SQLite: {result.db_path}")
    print("Next:")
    print("  Run:")
    print("    surepython diff")
    print("    surepython log --db <path>")
    return result.exit_code


def _cmd_add_return_type(
    file_path: Path,
    function: str,
    annotation: str,
    test: bool,
    test_command: str | None,
    dry_run: bool,
    db: Path | None,
    output_format: str,
) -> int:
    try:
        with acquire_project_mutation_lock(_mutation_root_for(file_path.parent), "add-return-type"):
            _ensure_no_recovery_required(_mutation_root_for(file_path.parent))
            result = add_return_type(
                file_path,
                function,
                annotation,
                project_root=file_path.parent,
                db_path=db,
                run_tests=test,
                test_command=test_command,
                dry_run=dry_run,
            )
    except GitError as exc:
        return _emit_error("add-return-type", exc, output_format, meta={"dry_run": dry_run, "format": output_format})

    if output_format == "json":
        _print_json_response(
            build_protocol_response(
                command="add-return-type",
                ok=result.exit_code == 0,
                status="preview" if dry_run else result.status,
                error=None
                if result.exit_code == 0
                else {
                    "code": "TESTS_FAILED",
                    "message": "pytest exited with a non-zero status",
                    "details": {"exit_code": result.pytest_exit_code},
                },
                result=_build_operation_result_payload("add-return-type", result, output_format, dry_run),
                meta={"dry_run": dry_run, "format": "json"},
            )
        )
        return result.exit_code

    print("SurePython v0.1")
    print(f"Project:\n  {result.project_root}")
    print("Operation:\n  add-return-type")
    print(f"Target:\n  {result.file_path.name}::{result.symbol}")
    print(f"Annotation:\n  {result.annotation}")
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
        print("  Added return annotation.")
        print("Diff:")
        if result.git_stat.strip():
            print(result.git_stat.rstrip())
        if result.git_diff_text.strip():
            print(result.git_diff_text.rstrip())
    if result.pytest_command:
        print("Test:")
        print(f"  {result.pytest_command} -> exit {result.pytest_exit_code}")
        if result.pytest_status:
            print(f"  Status: {result.pytest_status}")
    if result.logged:
        print("Log:")
        print(f"  SQLite: {result.db_path}")
    print("Next:")
    print("  Run:")
    print("    surepython diff")
    print("    surepython log --db <path>")
    return result.exit_code


def _cmd_remove_return_type(
    file_path: Path,
    function: str,
    expected_annotation: str,
    test: bool,
    test_command: str | None,
    dry_run: bool,
    db: Path | None,
    output_format: str,
) -> int:
    try:
        with acquire_project_mutation_lock(_mutation_root_for(file_path.parent), "remove-return-type"):
            _ensure_no_recovery_required(_mutation_root_for(file_path.parent))
            result = remove_return_type(
                file_path,
                function,
                expected_annotation,
                project_root=file_path.parent,
                db_path=db,
                run_tests=test,
                test_command=test_command,
                dry_run=dry_run,
            )
    except GitError as exc:
        return _emit_error(
            "remove-return-type",
            exc,
            output_format,
            meta={"dry_run": dry_run, "format": output_format},
        )

    if output_format == "json":
        _print_json_response(
            build_protocol_response(
                command="remove-return-type",
                ok=result.exit_code == 0,
                status="preview" if dry_run else result.status,
                error=None
                if result.exit_code == 0
                else {
                    "code": "TESTS_FAILED",
                    "message": "pytest exited with a non-zero status",
                    "details": {"exit_code": result.pytest_exit_code},
                },
                result=_build_operation_result_payload("remove-return-type", result, output_format, dry_run),
                meta={"dry_run": dry_run, "format": "json"},
            )
        )
        return result.exit_code

    print("SurePython v0.1")
    print(f"Project:\n  {result.project_root}")
    print("Operation:\n  remove-return-type")
    print(f"Target:\n  {result.file_path.name}::{result.symbol}")
    print(f"Expected annotation:\n  {result.expected_annotation}")
    print(f"Removed annotation:\n  {result.annotation}")
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
        print("  Removed return annotation.")
        print("Diff:")
        if result.git_stat.strip():
            print(result.git_stat.rstrip())
        if result.git_diff_text.strip():
            print(result.git_diff_text.rstrip())
    if result.pytest_command:
        print("Test:")
        print(f"  {result.pytest_command} -> exit {result.pytest_exit_code}")
        if result.pytest_status:
            print(f"  Status: {result.pytest_status}")
    if result.logged:
        print("Log:")
        print(f"  SQLite: {result.db_path}")
    print("Next:")
    print("  Run:")
    print("    surepython diff")
    print("    surepython log --db <path>")
    return result.exit_code


def _cmd_remove_parameter_type(
    file_path: Path,
    function: str,
    parameter: str,
    expected_annotation: str,
    test: bool,
    test_command: str | None,
    dry_run: bool,
    db: Path | None,
    output_format: str,
) -> int:
    try:
        with acquire_project_mutation_lock(_mutation_root_for(file_path.parent), "remove-parameter-type"):
            _ensure_no_recovery_required(_mutation_root_for(file_path.parent))
            result = remove_parameter_type(
                file_path,
                function,
                parameter,
                expected_annotation,
                project_root=file_path.parent,
                db_path=db,
                run_tests=test,
                test_command=test_command,
                dry_run=dry_run,
            )
    except GitError as exc:
        return _emit_error(
            "remove-parameter-type",
            exc,
            output_format,
            meta={"dry_run": dry_run, "format": output_format},
        )

    if output_format == "json":
        _print_json_response(
            build_protocol_response(
                command="remove-parameter-type",
                ok=result.exit_code == 0,
                status="preview" if dry_run else result.status,
                error=None
                if result.exit_code == 0
                else {
                    "code": "TESTS_FAILED",
                    "message": "pytest exited with a non-zero status",
                    "details": {"exit_code": result.pytest_exit_code},
                },
                result=_build_operation_result_payload("remove-parameter-type", result, output_format, dry_run),
                meta={"dry_run": dry_run, "format": "json"},
            )
        )
        return result.exit_code

    print("SurePython v0.1")
    print(f"Project:\n  {result.project_root}")
    print("Operation:\n  remove-parameter-type")
    print(f"Target:\n  {result.file_path.name}::{result.symbol}")
    print(f"Target kind:\n  {result.target_kind}")
    print(f"Parameter:\n  {result.parameter}")
    print(f"Parameter kind:\n  {result.parameter_kind}")
    print(f"Expected annotation:\n  {result.expected_annotation}")
    print(f"Removed annotation:\n  {result.removed_annotation}")
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
        print("  Removed parameter annotation.")
        print("Diff:")
        if result.git_stat.strip():
            print(result.git_stat.rstrip())
        if result.git_diff_text.strip():
            print(result.git_diff_text.rstrip())
    if result.pytest_command:
        print("Test:")
        print(f"  {result.pytest_command} -> exit {result.pytest_exit_code}")
        if result.pytest_status:
            print(f"  Status: {result.pytest_status}")
    if result.logged:
        print("Log:")
        print(f"  SQLite: {result.db_path}")
    print("Next:")
    print("  Run:")
    print("    surepython diff")
    print("    surepython log --db <path>")
    return result.exit_code


def _cmd_add_parameter_type(
    file_path: Path,
    function: str,
    parameter: str,
    annotation: str,
    test: bool,
    test_command: str | None,
    dry_run: bool,
    db: Path | None,
    output_format: str,
) -> int:
    try:
        with acquire_project_mutation_lock(_mutation_root_for(file_path.parent), "add-parameter-type"):
            _ensure_no_recovery_required(_mutation_root_for(file_path.parent))
            result = add_parameter_type(
                file_path,
                function,
                parameter,
                annotation,
                project_root=file_path.parent,
                db_path=db,
                run_tests=test,
                test_command=test_command,
                dry_run=dry_run,
            )
    except GitError as exc:
        return _emit_error("add-parameter-type", exc, output_format, meta={"dry_run": dry_run, "format": output_format})

    if output_format == "json":
        _print_json_response(
            build_protocol_response(
                command="add-parameter-type",
                ok=result.exit_code == 0,
                status="preview" if dry_run else result.status,
                error=None
                if result.exit_code == 0
                else {
                    "code": "TESTS_FAILED",
                    "message": "pytest exited with a non-zero status",
                    "details": {"exit_code": result.pytest_exit_code},
                },
                result=_build_operation_result_payload("add-parameter-type", result, output_format, dry_run),
                meta={"dry_run": dry_run, "format": "json"},
            )
        )
        return result.exit_code

    print("SurePython v0.1")
    print(f"Project:\n  {result.project_root}")
    print("Operation:\n  add-parameter-type")
    print(f"Target:\n  {result.file_path.name}::{result.symbol}")
    print(f"Parameter:\n  {result.parameter}")
    print(f"Annotation:\n  {result.annotation}")
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
        print("  Added parameter annotation.")
        print("Diff:")
        if result.git_stat.strip():
            print(result.git_stat.rstrip())
        if result.git_diff_text.strip():
            print(result.git_diff_text.rstrip())
    if result.pytest_command:
        print("Test:")
        print(f"  {result.pytest_command} -> exit {result.pytest_exit_code}")
        if result.pytest_status:
            print(f"  Status: {result.pytest_status}")
    if result.logged:
        print("Log:")
        print(f"  SQLite: {result.db_path}")
    print("Next:")
    print("  Run:")
    print("    surepython diff")
    print("    surepython log --db <path>")
    return result.exit_code


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


def _cmd_rollback(last: bool, operation_id: int | None, db: Path, dry_run: bool, output_format: str) -> int:
    try:
        current_root = _mutation_root_for(Path.cwd())
        with acquire_project_mutation_lock(current_root, "rollback"):
            if last and operation_id is not None:
                raise GitError(
                    "Rollback accepts either --last or --id, not both",
                    code="ROLLBACK_SELECTOR_CONFLICT",
                )
            if not last and operation_id is None:
                raise GitError("Rollback requires --last or --id", code="OPERATION_ID_REQUIRED")
            if operation_id is not None:
                result = rollback_by_id(db, operation_id, dry_run=dry_run, current_root=current_root)
            else:
                result = rollback_last(db, dry_run=dry_run)
    except FileNotFoundError as exc:
        return _emit_error(
            "rollback",
            GitError(str(exc), code="ROLLBACK_NOT_AVAILABLE"),
            output_format,
            meta={"dry_run": dry_run, "format": output_format},
        )
    except GitError as exc:
        return _emit_error("rollback", exc, output_format, meta={"dry_run": dry_run, "format": output_format})

    if output_format == "json":
        _print_json_response(
            build_protocol_response(
                command="rollback",
                ok=True,
                status="preview" if dry_run else result.status,
                error=None,
                result=_build_operation_result_payload("rollback", result, output_format, dry_run),
                meta={"dry_run": dry_run, "format": "json"},
            )
        )
        return result.exit_code

    print("SurePython v0.1")
    print(f"Project:\n  {result.project_root}")
    print("Operation:\n  rollback")
    print(f"Selector:\n  {result.selector_type} = {result.selector_value}")
    print(f"Target:\n  {result.file_path.name}::{result.symbol}")
    print("Mode:")
    print("  Dry run; no files changed." if dry_run else "  Applied rollback.")
    print("Rollback diff:")
    if result.preview_diff_text:
        print(result.preview_diff_text.rstrip())
    if result.logged:
        print("Log:")
        print(f"  SQLite: {result.db_path}")
    return result.exit_code


def _cmd_plan_preview(plan_path: Path, output_format: str) -> int:
    try:
        with acquire_project_mutation_lock(_mutation_root_for(Path.cwd()), "plan preview"):
            result = preview_plan(plan_path, project_root=Path.cwd())
    except GitError as exc:
        return _emit_error(
            "plan",
            exc,
            output_format,
            meta={"action": "preview", "format": output_format},
        )

    if output_format == "json":
        _print_json_response(
            build_protocol_response(
                command="plan",
                ok=True,
                status="preview",
                error=None,
                result=_build_plan_result_payload(result),
                meta={"action": "preview", "format": "json"},
            )
        )
        return 0

    print("SurePython v0.1")
    print(f"Project:\n  {Path.cwd()}")
    print("Operation:\n  plan preview")
    print(f"Plan:\n  {plan_path}")
    print(f"Preview hash:\n  {result.preview_hash}")
    print("Steps:")
    for step in result.steps:
        print(f"  {step['index'] + 1}. {step['operation']} {step['file']} ({step['status']})")
    print("Diff:")
    if result.final_diff.strip():
        print(result.final_diff.rstrip())
    return 0


def _cmd_plan_apply(plan_path: Path, expected_preview_hash: str, test: bool, db: Path, output_format: str) -> int:
    try:
        with acquire_project_mutation_lock(_mutation_root_for(Path.cwd()), "plan apply"):
            result = apply_plan(
                plan_path,
                expected_preview_hash,
                project_root=Path.cwd(),
                db_path=db,
                run_tests=test,
            )
    except GitError as exc:
        return _emit_error(
            "plan",
            exc,
            output_format,
            meta={"action": "apply", "format": output_format, "test": test},
        )

    if output_format == "json":
        _print_json_response(
            build_protocol_response(
                command="plan",
                ok=True,
                status=result.status,
                error=None,
                result=_build_plan_result_payload(result),
                meta={"action": "apply", "format": "json", "test": test},
            )
        )
        return 0

    print("SurePython v0.1")
    print(f"Project:\n  {Path.cwd()}")
    print("Operation:\n  plan apply")
    print(f"Plan:\n  {plan_path}")
    print(f"Preview hash:\n  {result.preview_hash}")
    print("Applied:")
    print(f"  Steps: {result.step_count}")
    print(f"  Files: {result.file_count}")
    print("Diff:")
    if result.final_diff.strip():
        print(result.final_diff.rstrip())
    if result.pytest_command:
        print("Test:")
        print(f"  {result.pytest_command} -> exit {result.pytest_exit_code}")
        if result.pytest_status:
            print(f"  Status: {result.pytest_status}")
    if result.logged:
        print("Log:")
        print(f"  SQLite: {result.plan_operation_id}")
    return 0


def _cmd_plan_rollback(
    last: bool,
    plan_id: int | None,
    db: Path,
    dry_run: bool,
    output_format: str,
) -> int:
    try:
        with acquire_project_mutation_lock(_mutation_root_for(Path.cwd()), "plan rollback"):
            result = rollback_transactional_plan(
                db,
                plan_id=plan_id,
                last=last,
                project_root=Path.cwd(),
                dry_run=dry_run,
            )
    except GitError as exc:
        return _emit_error(
            "plan",
            exc,
            output_format,
            meta={"action": "rollback", "dry_run": dry_run, "format": output_format},
        )

    if output_format == "json":
        _print_json_response(
            build_protocol_response(
                command="plan",
                ok=True,
                status=result.status,
                error=None,
                result=_build_plan_result_payload(result),
                meta={"action": "rollback", "dry_run": dry_run, "format": "json"},
            )
        )
        return 0

    print("SurePython v0.1")
    print(f"Project:\n  {Path.cwd()}")
    print("Operation:\n  plan rollback")
    print(f"Selector:\n  {result.selector_type} = {result.selector_value}")
    print(f"Plan id:\n  {result.source_plan_operation_id}")
    print("Mode:")
    print("  Dry run; no files changed." if dry_run else "  Applied rollback.")
    print("Rollback diff:")
    if result.final_diff.strip():
        print(result.final_diff.rstrip())
    if result.logged:
        print("Log:")
        print(f"  SQLite: {result.plan_operation_id}")
    return 0


def _cmd_plan_recover(output_format: str) -> int:
    try:
        with acquire_project_mutation_lock(_mutation_root_for(Path.cwd()), "plan recover"):
            result = recover_plan(project_root=Path.cwd())
    except GitError as exc:
        return _emit_error(
            "plan",
            exc,
            output_format,
            meta={"action": "recover", "format": output_format},
        )

    status = "recovered" if result.get("recovered") else result.get("status", "noop")
    if output_format == "json":
        _print_json_response(
            build_protocol_response(
                command="plan",
                ok=True,
                status=status,
                error=None,
                result=result,
                meta={"action": "recover", "format": "json"},
            )
        )
        return 0

    print("SurePython v0.1")
    print(f"Project:\n  {Path.cwd()}")
    print("Operation:\n  plan recover")
    print(f"Status:\n  {status}")
    print(f"Recovered:\n  {'yes' if result.get('recovered') else 'no'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="surepython", description="SurePython v0.1")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Scan Python symbols")
    scan_parser.add_argument("path", type=Path)
    scan_parser.add_argument("--format", choices=["text", "json", "csv"], default="text")

    capabilities_parser = subparsers.add_parser("capabilities", help="Show supported operations")
    capabilities_parser.add_argument("--format", choices=["text", "json"], default="text")

    plan_parser = subparsers.add_parser("plan", help="Transactional multi-operation plans")
    plan_subparsers = plan_parser.add_subparsers(dest="plan_command", required=True)

    plan_preview_parser = plan_subparsers.add_parser("preview", help="Preview a transactional plan")
    plan_preview_parser.add_argument("plan_path", type=Path)
    plan_preview_parser.add_argument("--format", choices=["text", "json"], default="text")

    plan_apply_parser = plan_subparsers.add_parser("apply", help="Apply a transactional plan")
    plan_apply_parser.add_argument("plan_path", type=Path)
    plan_apply_parser.add_argument("--expect-preview-hash")
    plan_apply_parser.add_argument("--test", action="store_true")
    plan_apply_parser.add_argument("--db", type=Path, required=True)
    plan_apply_parser.add_argument("--format", choices=["text", "json"], default="text")

    plan_rollback_parser = plan_subparsers.add_parser("rollback", help="Rollback a transactional plan")
    plan_rollback_parser.add_argument("--last", action="store_true")
    plan_rollback_parser.add_argument("--id", type=int)
    plan_rollback_parser.add_argument("--db", type=Path, required=True)
    plan_rollback_parser.add_argument("--dry-run", action="store_true")
    plan_rollback_parser.add_argument("--format", choices=["text", "json"], default="text")

    plan_subparsers.add_parser("recover", help="Recover an interrupted transactional plan").add_argument(
        "--format", choices=["text", "json"], default="text"
    )

    add_parser = subparsers.add_parser("add-docstring", help="Add a skeleton docstring")
    add_parser.add_argument("file_path", type=Path)
    add_parser.add_argument("--function", required=True)
    add_parser.add_argument("--test", action="store_true")
    add_parser.add_argument("--test-command")
    add_parser.add_argument("--dry-run", action="store_true")
    add_parser.add_argument("--db", type=Path)
    add_parser.add_argument("--format", choices=["text", "json"], default="text")

    remove_docstring_parser = subparsers.add_parser(
        "remove-docstring", help="Remove an exact docstring after verifying the expected text"
    )
    remove_docstring_parser.add_argument("file_path", type=Path)
    remove_docstring_parser.add_argument("--symbol", required=True)
    remove_docstring_parser.add_argument("--expect-docstring", required=True)
    remove_docstring_parser.add_argument("--test", action="store_true")
    remove_docstring_parser.add_argument("--test-command")
    remove_docstring_parser.add_argument("--dry-run", action="store_true")
    remove_docstring_parser.add_argument("--db", type=Path)
    remove_docstring_parser.add_argument("--format", choices=["text", "json"], default="text")

    import_parser = subparsers.add_parser("add-import", help="Add an explicit import statement")
    import_parser.add_argument("file_path", type=Path)
    import_parser.add_argument("--statement", required=True)
    import_parser.add_argument("--test", action="store_true")
    import_parser.add_argument("--test-command")
    import_parser.add_argument("--dry-run", action="store_true")
    import_parser.add_argument("--db", type=Path)
    import_parser.add_argument("--format", choices=["text", "json"], default="text")

    remove_import_parser = subparsers.add_parser(
        "remove-import",
        help="Remove an explicit module-level import statement after verifying the expected statement",
    )
    remove_import_parser.add_argument("file_path", type=Path)
    remove_import_parser.add_argument("--expect-statement", required=True)
    remove_import_parser.add_argument("--test", action="store_true")
    remove_import_parser.add_argument("--test-command")
    remove_import_parser.add_argument("--dry-run", action="store_true")
    remove_import_parser.add_argument("--db", type=Path)
    remove_import_parser.add_argument("--format", choices=["text", "json"], default="text")

    decorator_parser = subparsers.add_parser("add-decorator", help="Add an explicit decorator")
    decorator_parser.add_argument("file_path", type=Path)
    decorator_parser.add_argument("--symbol")
    decorator_parser.add_argument("--decorator")
    decorator_parser.add_argument("--position")
    decorator_parser.add_argument("--test", action="store_true")
    decorator_parser.add_argument("--test-command")
    decorator_parser.add_argument("--dry-run", action="store_true")
    decorator_parser.add_argument("--db", type=Path)
    decorator_parser.add_argument("--format", choices=["text", "json"], default="text")

    remove_decorator_parser = subparsers.add_parser(
        "remove-decorator",
        help="Remove an explicit decorator after verifying the expected expression and position",
    )
    remove_decorator_parser.add_argument("file_path", type=Path)
    remove_decorator_parser.add_argument("--symbol")
    remove_decorator_parser.add_argument("--expect-decorator")
    remove_decorator_parser.add_argument("--expect-position")
    remove_decorator_parser.add_argument("--test", action="store_true")
    remove_decorator_parser.add_argument("--test-command")
    remove_decorator_parser.add_argument("--dry-run", action="store_true")
    remove_decorator_parser.add_argument("--db", type=Path)
    remove_decorator_parser.add_argument("--format", choices=["text", "json"], default="text")

    return_parser = subparsers.add_parser("add-return-type", help="Add an explicit return annotation")
    return_parser.add_argument("file_path", type=Path)
    return_parser.add_argument("--function", required=True)
    return_parser.add_argument("--annotation", required=True)
    return_parser.add_argument("--test", action="store_true")
    return_parser.add_argument("--test-command")
    return_parser.add_argument("--dry-run", action="store_true")
    return_parser.add_argument("--db", type=Path)
    return_parser.add_argument("--format", choices=["text", "json"], default="text")

    remove_return_parser = subparsers.add_parser(
        "remove-return-type", help="Remove an explicit return annotation after verifying the expected value"
    )
    remove_return_parser.add_argument("file_path", type=Path)
    remove_return_parser.add_argument("--function", required=True)
    remove_return_parser.add_argument("--expect-annotation", required=True)
    remove_return_parser.add_argument("--test", action="store_true")
    remove_return_parser.add_argument("--test-command")
    remove_return_parser.add_argument("--dry-run", action="store_true")
    remove_return_parser.add_argument("--db", type=Path)
    remove_return_parser.add_argument("--format", choices=["text", "json"], default="text")

    remove_parameter_parser = subparsers.add_parser(
        "remove-parameter-type",
        help="Remove an explicit parameter annotation after verifying the expected value",
    )
    remove_parameter_parser.add_argument("file_path", type=Path)
    remove_parameter_parser.add_argument("--function", required=True)
    remove_parameter_parser.add_argument("--parameter", required=True)
    remove_parameter_parser.add_argument("--expect-annotation", required=True)
    remove_parameter_parser.add_argument("--test", action="store_true")
    remove_parameter_parser.add_argument("--test-command")
    remove_parameter_parser.add_argument("--dry-run", action="store_true")
    remove_parameter_parser.add_argument("--db", type=Path)
    remove_parameter_parser.add_argument("--format", choices=["text", "json"], default="text")

    parameter_parser = subparsers.add_parser("add-parameter-type", help="Add an explicit parameter annotation")
    parameter_parser.add_argument("file_path", type=Path)
    parameter_parser.add_argument("--function", required=True)
    parameter_parser.add_argument("--parameter", required=True)
    parameter_parser.add_argument("--annotation", required=True)
    parameter_parser.add_argument("--test", action="store_true")
    parameter_parser.add_argument("--test-command")
    parameter_parser.add_argument("--dry-run", action="store_true")
    parameter_parser.add_argument("--db", type=Path)
    parameter_parser.add_argument("--format", choices=["text", "json"], default="text")

    subparsers.add_parser("diff", help="Show git diff")

    log_parser = subparsers.add_parser("log", help="Log the last operation to SQLite")
    log_parser.add_argument("--db", type=Path, required=True)

    rollback_parser = subparsers.add_parser("rollback", help="Rollback a logged operation")
    rollback_parser.add_argument("--last", action="store_true")
    rollback_parser.add_argument("--id", type=int)
    rollback_parser.add_argument("--db", type=Path, required=True)
    rollback_parser.add_argument("--dry-run", action="store_true")
    rollback_parser.add_argument("--format", choices=["text", "json"], default="text")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "scan":
            return _cmd_scan(args.path, args.format)
        if args.command == "capabilities":
            return _cmd_capabilities(args.format)
        if args.command == "plan":
            if args.plan_command == "preview":
                return _cmd_plan_preview(args.plan_path, args.format)
            if args.plan_command == "apply":
                return _cmd_plan_apply(
                    args.plan_path,
                    args.expect_preview_hash,
                    args.test,
                    args.db,
                    args.format,
                )
            if args.plan_command == "rollback":
                return _cmd_plan_rollback(
                    args.last,
                    getattr(args, "id", None),
                    args.db,
                    args.dry_run,
                    args.format,
                )
            if args.plan_command == "recover":
                return _cmd_plan_recover(args.format)
            parser.error("unknown plan command")
            return 2
        if args.command == "add-docstring":
            return _cmd_add_docstring(
                args.file_path,
                args.function,
                args.test,
                args.test_command,
                args.dry_run,
                args.db,
                args.format,
            )
        if args.command == "remove-docstring":
            return _cmd_remove_docstring(
                args.file_path,
                args.symbol,
                args.expect_docstring,
                args.test,
                args.test_command,
                args.dry_run,
                args.db,
                args.format,
            )
        if args.command == "add-return-type":
            return _cmd_add_return_type(
                args.file_path,
                args.function,
                args.annotation,
                args.test,
                args.test_command,
                args.dry_run,
                args.db,
                args.format,
            )
        if args.command == "remove-return-type":
            return _cmd_remove_return_type(
                args.file_path,
                args.function,
                args.expect_annotation,
                args.test,
                args.test_command,
                args.dry_run,
                args.db,
                args.format,
            )
        if args.command == "remove-parameter-type":
            return _cmd_remove_parameter_type(
                args.file_path,
                args.function,
                args.parameter,
                args.expect_annotation,
                args.test,
                args.test_command,
                args.dry_run,
                args.db,
                args.format,
            )
        if args.command == "add-parameter-type":
            return _cmd_add_parameter_type(
                args.file_path,
                args.function,
                args.parameter,
                args.annotation,
                args.test,
                args.test_command,
                args.dry_run,
                args.db,
                args.format,
            )
        if args.command == "add-import":
            return _cmd_add_import(
                args.file_path,
                args.statement,
                args.test,
                args.test_command,
                args.dry_run,
                args.db,
                args.format,
            )
        if args.command == "remove-import":
            return _cmd_remove_import(
                args.file_path,
                args.expect_statement,
                args.test,
                args.test_command,
                args.dry_run,
                args.db,
                args.format,
            )
        if args.command == "add-decorator":
            return _cmd_add_decorator(
                args.file_path,
                args.symbol,
                args.decorator,
                args.position,
                args.test,
                args.test_command,
                args.dry_run,
                args.db,
                args.format,
            )
        if args.command == "remove-decorator":
            return _cmd_remove_decorator(
                args.file_path,
                args.symbol,
                args.expect_decorator,
                args.expect_position,
                args.test,
                args.test_command,
                args.dry_run,
                args.db,
                args.format,
            )
        if args.command == "diff":
            return _cmd_diff()
        if args.command == "log":
            return _cmd_log(args.db)
        if args.command == "rollback":
            return _cmd_rollback(args.last, getattr(args, "id", None), args.db, args.dry_run, args.format)
        parser.error("unknown command")
        return 2
    except ProtocolError as exc:
        return _emit_error(
            args.command,
            exc,
            getattr(args, "format", "text"),
            meta={"dry_run": getattr(args, "dry_run", False), "format": getattr(args, "format", "text")},
        )
    except Exception as exc:  # pragma: no cover - defensive
        if getattr(args, "format", "text") == "json":
            _print_json_response(
                build_protocol_response(
                    command=args.command,
                    ok=False,
                    status="failed",
                    error={
                        "code": "INTERNAL_ERROR",
                        "message": str(exc) or "internal error",
                        "details": {},
                    },
                    result=None,
                    meta={"dry_run": getattr(args, "dry_run", False), "format": "json"},
                )
            )
            return EXIT_INTERNAL
        _print_error(str(exc))
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
