from __future__ import annotations

import json
from typing import Any


PROTOCOL_SCHEMA_VERSION = "1.0"
CAPABILITIES_SCHEMA_VERSION = "1.0"

EXIT_SUCCESS = 0
EXIT_REFUSED = 2
EXIT_TESTS_FAILED = 3
EXIT_SECURITY = 4
EXIT_INTERNAL = 5

ERROR_CODES = (
    "GIT_NOT_REPOSITORY",
    "GIT_DIRTY",
    "FILE_OUTSIDE_PROJECT",
    "FILE_NOT_FOUND",
    "PARSE_ERROR",
    "TARGET_NOT_FOUND",
    "TARGET_AMBIGUOUS",
    "TARGET_UNSUPPORTED",
    "DOCSTRING_EXISTS",
    "ANNOTATION_REQUIRED",
    "ANNOTATION_INVALID",
    "ANNOTATION_EXISTS",
    "UNSUPPORTED_OPERATION",
    "UNKNOWN_SQLITE_OPERATION",
    "HASH_MISMATCH",
    "LEGACY_UNVERIFIABLE",
    "TESTS_FAILED",
    "DATABASE_ERROR",
    "ROLLBACK_NOT_AVAILABLE",
    "INTERNAL_ERROR",
)

EXIT_CODE_BY_ERROR_CODE = {
    "GIT_NOT_REPOSITORY": EXIT_REFUSED,
    "GIT_DIRTY": EXIT_REFUSED,
    "FILE_OUTSIDE_PROJECT": EXIT_REFUSED,
    "FILE_NOT_FOUND": EXIT_REFUSED,
    "PARSE_ERROR": EXIT_REFUSED,
    "TARGET_NOT_FOUND": EXIT_REFUSED,
    "TARGET_AMBIGUOUS": EXIT_REFUSED,
    "TARGET_UNSUPPORTED": EXIT_REFUSED,
    "DOCSTRING_EXISTS": EXIT_REFUSED,
    "ANNOTATION_REQUIRED": EXIT_REFUSED,
    "ANNOTATION_INVALID": EXIT_REFUSED,
    "ANNOTATION_EXISTS": EXIT_REFUSED,
    "UNSUPPORTED_OPERATION": EXIT_REFUSED,
    "UNKNOWN_SQLITE_OPERATION": EXIT_REFUSED,
    "HASH_MISMATCH": EXIT_SECURITY,
    "LEGACY_UNVERIFIABLE": EXIT_SECURITY,
    "TESTS_FAILED": EXIT_TESTS_FAILED,
    "DATABASE_ERROR": EXIT_INTERNAL,
    "ROLLBACK_NOT_AVAILABLE": EXIT_REFUSED,
    "INTERNAL_ERROR": EXIT_INTERNAL,
}


class ProtocolError(RuntimeError):
    def __init__(self, message: str, *, code: str = "INTERNAL_ERROR", details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}

    @property
    def exit_code(self) -> int:
        return EXIT_CODE_BY_ERROR_CODE.get(self.code, EXIT_INTERNAL)

    def to_payload(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": str(self),
            "details": self.details,
        }


def dump_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)


def build_protocol_response(
    *,
    command: str,
    ok: bool,
    status: str,
    error: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "protocol_schema_version": PROTOCOL_SCHEMA_VERSION,
        "command": command,
        "ok": ok,
        "status": status,
        "error": error,
        "result": result,
        "meta": meta or {},
    }


def build_capabilities_payload(operations: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "protocol_schema_version": PROTOCOL_SCHEMA_VERSION,
        "capabilities_schema_version": CAPABILITIES_SCHEMA_VERSION,
        "operations": operations,
    }
