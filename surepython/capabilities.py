from __future__ import annotations

from dataclasses import asdict, dataclass
import json

from .protocol import build_capabilities_payload

@dataclass(frozen=True)
class OperationCapability:
    name: str
    description: str
    targets: list[str]
    required_arguments: list[str]
    optional_arguments: list[str]
    supported_parameter_kinds: list[str]
    unsupported_parameter_kinds: list[str]
    supports_dry_run: bool
    supports_tests: bool
    supports_logging: bool
    supports_rollback: bool
    supported_formats: list[str]
    possible_error_codes: list[str]
    status: str


@dataclass(frozen=True)
class CommandCapability:
    name: str
    description: str
    required_arguments: list[str]
    optional_arguments: list[str]
    selectors: list[str]
    mutually_exclusive_selectors: bool
    supported_formats: list[str]
    possible_error_codes: list[str]
    status: str


OPERATIONS = [
    OperationCapability(
        name="add-docstring",
        description="Add one skeleton docstring to one function or method without an existing docstring.",
        targets=["function", "method"],
        required_arguments=["file", "function"],
        optional_arguments=["dry-run", "test", "db", "format"],
        supported_parameter_kinds=[],
        unsupported_parameter_kinds=[],
        supports_dry_run=True,
        supports_tests=True,
        supports_logging=True,
        supports_rollback=True,
        supported_formats=["text", "json"],
        possible_error_codes=[
            "GIT_NOT_REPOSITORY",
            "GIT_DIRTY",
            "FILE_NOT_FOUND",
            "FILE_OUTSIDE_PROJECT",
            "TARGET_NOT_FOUND",
            "TARGET_AMBIGUOUS",
            "DOCSTRING_EXISTS",
            "PARSE_ERROR",
            "TESTS_FAILED",
            "UNKNOWN_SQLITE_OPERATION",
            "HASH_MISMATCH",
            "LEGACY_UNVERIFIABLE",
            "DATABASE_ERROR",
            "INTERNAL_ERROR",
        ],
        status="stable",
    ),
    OperationCapability(
        name="add-return-type",
        description="Add one explicit return annotation to one function or method without an existing return annotation.",
        targets=["function", "method"],
        required_arguments=["file", "function", "annotation"],
        optional_arguments=["dry-run", "test", "db", "format"],
        supported_parameter_kinds=[],
        unsupported_parameter_kinds=[],
        supports_dry_run=True,
        supports_tests=True,
        supports_logging=True,
        supports_rollback=True,
        supported_formats=["text", "json"],
        possible_error_codes=[
            "GIT_NOT_REPOSITORY",
            "GIT_DIRTY",
            "FILE_NOT_FOUND",
            "FILE_OUTSIDE_PROJECT",
            "TARGET_NOT_FOUND",
            "TARGET_AMBIGUOUS",
            "TARGET_UNSUPPORTED",
            "ANNOTATION_REQUIRED",
            "ANNOTATION_INVALID",
            "ANNOTATION_EXISTS",
            "PARSE_ERROR",
            "TESTS_FAILED",
            "UNKNOWN_SQLITE_OPERATION",
            "HASH_MISMATCH",
            "LEGACY_UNVERIFIABLE",
            "DATABASE_ERROR",
            "INTERNAL_ERROR",
        ],
        status="experimental",
    ),
    OperationCapability(
        name="add-parameter-type",
        description="Add one explicit type annotation to one parameter on one function or method without an existing annotation.",
        targets=["function", "method"],
        required_arguments=["file", "function", "parameter", "annotation"],
        optional_arguments=["dry-run", "test", "db", "format"],
        supported_parameter_kinds=["positional-only", "positional-or-keyword", "keyword-only"],
        unsupported_parameter_kinds=["var-positional", "var-keyword"],
        supports_dry_run=True,
        supports_tests=True,
        supports_logging=True,
        supports_rollback=True,
        supported_formats=["text", "json"],
        possible_error_codes=[
            "GIT_NOT_REPOSITORY",
            "GIT_DIRTY",
            "FILE_NOT_FOUND",
            "FILE_OUTSIDE_PROJECT",
            "TARGET_NOT_FOUND",
            "TARGET_AMBIGUOUS",
            "TARGET_UNSUPPORTED",
            "PARAMETER_REQUIRED",
            "PARAMETER_NOT_FOUND",
            "PARAMETER_ANNOTATION_EXISTS",
            "PARAMETER_KIND_UNSUPPORTED",
            "ANNOTATION_REQUIRED",
            "ANNOTATION_INVALID",
            "PARSE_ERROR",
            "TESTS_FAILED",
            "UNKNOWN_SQLITE_OPERATION",
            "HASH_MISMATCH",
            "LEGACY_UNVERIFIABLE",
            "DATABASE_ERROR",
            "INTERNAL_ERROR",
        ],
        status="experimental",
    ),
    OperationCapability(
        name="add-import",
        description="Add one explicit top-level import statement with a single binding to one module file.",
        targets=["module"],
        required_arguments=["file", "statement"],
        optional_arguments=["dry-run", "test", "db", "format"],
        supported_parameter_kinds=[],
        unsupported_parameter_kinds=[],
        supports_dry_run=True,
        supports_tests=True,
        supports_logging=True,
        supports_rollback=True,
        supported_formats=["text", "json"],
        possible_error_codes=[
            "GIT_NOT_REPOSITORY",
            "GIT_DIRTY",
            "FILE_NOT_FOUND",
            "FILE_OUTSIDE_PROJECT",
            "IMPORT_STATEMENT_REQUIRED",
            "IMPORT_STATEMENT_INVALID",
            "IMPORT_MULTIPLE_BINDINGS_UNSUPPORTED",
            "IMPORT_WILDCARD_UNSUPPORTED",
            "IMPORT_RELATIVE_UNSUPPORTED",
            "IMPORT_ALREADY_EXISTS",
            "IMPORT_BINDING_CONFLICT",
            "IMPORT_PLACEMENT_UNSUPPORTED",
            "PARSE_ERROR",
            "TESTS_FAILED",
            "UNKNOWN_SQLITE_OPERATION",
            "HASH_MISMATCH",
            "LEGACY_UNVERIFIABLE",
            "DATABASE_ERROR",
            "INTERNAL_ERROR",
        ],
        status="experimental",
    ),
]


COMMANDS = [
    CommandCapability(
        name="rollback",
        description="Rollback one previously logged operation by --last or by explicit operation id.",
        required_arguments=["db"],
        optional_arguments=["last", "id", "dry-run", "format"],
        selectors=["last", "id"],
        mutually_exclusive_selectors=True,
        supported_formats=["text", "json"],
        possible_error_codes=[
            "OPERATION_ID_REQUIRED",
            "OPERATION_ID_INVALID",
            "OPERATION_NOT_FOUND",
            "ROLLBACK_SELECTOR_CONFLICT",
            "ROLLBACK_ALREADY_APPLIED",
            "ROLLBACK_RECORD_NOT_ALLOWED",
            "PROJECT_MISMATCH",
            "GIT_DIRTY",
            "UNKNOWN_SQLITE_OPERATION",
            "HASH_MISMATCH",
            "LEGACY_UNVERIFIABLE",
            "ROLLBACK_NOT_AVAILABLE",
            "DATABASE_ERROR",
            "INTERNAL_ERROR",
        ],
        status="stable",
    ),
]


def capabilities_payload() -> dict[str, object]:
    return build_capabilities_payload(
        [asdict(operation) for operation in OPERATIONS],
        [asdict(command) for command in COMMANDS],
    )


def serialize_capabilities(output_format: str) -> str:
    payload = capabilities_payload()
    if output_format == "json":
        return json.dumps(payload, indent=2, ensure_ascii=False)
    if output_format == "text":
        lines = ["operations"]
        for operation in OPERATIONS:
            lines.append(f"- {operation.name}: {operation.description}")
        lines.append("commands")
        for command in COMMANDS:
            lines.append(f"- {command.name}: {command.description}")
        return "\n".join(lines)
    raise ValueError(f"Unsupported capabilities format: {output_format}")
