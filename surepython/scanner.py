from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SymbolRecord:
    file: str
    type: str
    name: str
    qualified_name: str
    line_start: int
    line_end: int
    has_docstring: bool


def _has_docstring(node: ast.AST) -> bool:
    return ast.get_docstring(node) is not None


def _record_from_node(file_path: Path, node_type: str, name: str, qualified_name: str, node: ast.AST) -> SymbolRecord:
    line_start = getattr(node, "lineno", 0) or 0
    line_end = getattr(node, "end_lineno", line_start) or line_start
    return SymbolRecord(
        file=str(file_path),
        type=node_type,
        name=name,
        qualified_name=qualified_name,
        line_start=line_start,
        line_end=line_end,
        has_docstring=_has_docstring(node),
    )


def scan_file(file_path: Path) -> list[SymbolRecord]:
    source = file_path.read_text(encoding="utf-8-sig")
    module = ast.parse(source, filename=str(file_path))
    records: list[SymbolRecord] = []

    def visit_class(node: ast.ClassDef, prefix: list[str]) -> None:
        qname = ".".join([*prefix, node.name])
        records.append(_record_from_node(file_path, "class", node.name, qname, node))
        for child in node.body:
            if isinstance(child, ast.ClassDef):
                visit_class(child, [*prefix, node.name])
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                child_qname = ".".join([*prefix, node.name, child.name])
                records.append(_record_from_node(file_path, "method", child.name, child_qname, child))

    for node in module.body:
        if isinstance(node, ast.ClassDef):
            visit_class(node, [])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            records.append(_record_from_node(file_path, "function", node.name, node.name, node))

    return records


def scan_project(root: Path) -> list[SymbolRecord]:
    records: list[SymbolRecord] = []
    for file_path in sorted(root.rglob("*.py")):
        if "__pycache__" in file_path.parts:
            continue
        records.extend(scan_file(file_path))
    return records
