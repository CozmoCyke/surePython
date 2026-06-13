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
    supports_dry_run: bool
    supports_tests: bool
    supports_logging: bool
    supports_rollback: bool
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
]


def capabilities_payload() -> dict[str, object]:
    return build_capabilities_payload([asdict(operation) for operation in OPERATIONS])


def serialize_capabilities(output_format: str) -> str:
    payload = capabilities_payload()
    if output_format == "json":
        return json.dumps(payload, indent=2, ensure_ascii=False)
    if output_format == "text":
        lines = ["operations"]
        for operation in OPERATIONS:
            lines.append(f"- {operation.name}: {operation.description}")
        return "\n".join(lines)
    raise ValueError(f"Unsupported capabilities format: {output_format}")
