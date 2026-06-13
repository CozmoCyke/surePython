from __future__ import annotations

from dataclasses import asdict, dataclass
import json


@dataclass(frozen=True)
class OperationCapability:
    name: str
    description: str
    targets: list[str]
    required_arguments: list[str]
    supports_dry_run: bool
    supports_tests: bool
    supports_logging: bool
    supports_rollback: bool
    status: str


OPERATIONS = [
    OperationCapability(
        name="add-docstring",
        description="Add one skeleton docstring to one function or method without an existing docstring.",
        targets=["function", "method"],
        required_arguments=["file", "function"],
        supports_dry_run=True,
        supports_tests=True,
        supports_logging=True,
        supports_rollback=True,
        status="stable",
    ),
    OperationCapability(
        name="add-return-type",
        description="Add one explicit return annotation to one function or method without an existing return annotation.",
        targets=["function", "method"],
        required_arguments=["file", "function", "annotation"],
        supports_dry_run=True,
        supports_tests=True,
        supports_logging=True,
        supports_rollback=True,
        status="experimental",
    ),
]


def capabilities_payload() -> dict[str, object]:
    return {"operations": [asdict(operation) for operation in OPERATIONS]}


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
