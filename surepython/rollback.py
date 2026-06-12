from __future__ import annotations

import difflib
import hashlib
from dataclasses import dataclass
from pathlib import Path

import libcst as cst

from .codemods import TODO_DOCSTRING
from .datasette_log import (
    OperationRecord,
    insert_record,
    now_utc_iso,
    read_last_add_docstring_operation,
    write_last_operation,
)
from .git_tools import GitError, ensure_clean_git_repo, is_within_root, sha256_file


@dataclass(frozen=True)
class RollbackResult:
    db_path: Path
    project_root: Path
    file_path: Path
    symbol: str
    dry_run: bool
    before_sha256: str
    after_sha256: str
    preview_diff_text: str
    status: str
    message: str


def _preview_diff(file_path: Path, before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=str(file_path),
            tofile=str(file_path),
        )
    ).rstrip("\n")


def _decode_python_bytes(data: bytes) -> tuple[str, bytes, str]:
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8"), b"\xef\xbb\xbf", "utf-8"
    return data.decode("utf-8"), b"", "utf-8"


def _encode_python_text(text: str, bom: bytes, encoding: str) -> bytes:
    return bom + text.encode(encoding)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _newline_variants(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    variants = [text, normalized, normalized.replace("\n", "\r\n")]
    unique: list[str] = []
    for variant in variants:
        if variant not in unique:
            unique.append(variant)
    return unique


def _bom_variants(current_bom: bytes) -> list[bytes]:
    variants = [current_bom, b"\xef\xbb\xbf" if current_bom == b"" else b""]
    unique: list[bytes] = []
    for variant in variants:
        if variant not in unique:
            unique.append(variant)
    return unique


def _split_lines_keepends(data: bytes) -> list[bytes]:
    return data.splitlines(keepends=True)


def _byte_line_removal_candidates(
    source_bytes: bytes,
    restored_source: str,
    *,
    bom: bytes,
    encoding: str,
) -> list[bytes]:
    lines = _split_lines_keepends(source_bytes)
    candidates: list[bytes] = []
    encoded_docstring = TODO_DOCSTRING.encode(encoding)

    for index, line in enumerate(lines):
        if encoded_docstring not in line:
            continue
        candidate = b"".join([*lines[:index], *lines[index + 1 :]])
        try:
            decoded, _, _ = _decode_python_bytes(candidate)
        except UnicodeDecodeError:
            continue
        if decoded == restored_source and candidate not in candidates:
            candidates.append(candidate)

    if bom and not source_bytes.startswith(bom):
        return candidates
    return candidates


def _select_restored_bytes(
    source_bytes: bytes,
    restored_source: str,
    *,
    current_bom: bytes,
    encoding: str,
    expected_sha256: str,
) -> bytes:
    for candidate in _byte_line_removal_candidates(
        source_bytes,
        restored_source,
        bom=current_bom,
        encoding=encoding,
    ):
        if _sha256_bytes(candidate) == expected_sha256:
            return candidate

    for text_variant in _newline_variants(restored_source):
        for bom_variant in _bom_variants(current_bom):
            candidate = _encode_python_text(text_variant, bom_variant, encoding)
            if _sha256_bytes(candidate) == expected_sha256:
                return candidate
    raise GitError("Rollback result does not match logged before_sha256")


class _DocstringRemover(cst.CSTTransformer):
    def __init__(self, target_qname: str) -> None:
        self.target_qname = target_qname
        self.scope: list[str] = []
        self.function_stack: list[bool] = []
        self.matched = False

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        self.scope.append(node.name.value)

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.CSTNode:
        self.scope.pop()
        return updated_node

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        qname = ".".join([*self.scope, node.name.value])
        self.function_stack.append(qname == self.target_qname)

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.CSTNode:
        is_target = self.function_stack.pop()
        if not is_target:
            return updated_node

        body = updated_node.body.body
        if not body:
            raise GitError("Target function body is empty")

        first_stmt = body[0]
        if not (
            isinstance(first_stmt, cst.SimpleStatementLine)
            and len(first_stmt.body) == 1
            and isinstance(first_stmt.body[0], cst.Expr)
            and isinstance(first_stmt.body[0].value, cst.SimpleString)
            and first_stmt.body[0].value.value == TODO_DOCSTRING
        ):
            raise GitError("Target does not contain the SurePython skeleton docstring")

        self.matched = True
        return updated_node.with_changes(
            body=updated_node.body.with_changes(body=body[1:])
        )


def _require_record_fields(record: OperationRecord) -> None:
    missing = [
        name
        for name in ("file_path", "operation", "symbol", "before_sha256", "after_sha256")
        if not getattr(record, name)
    ]
    if missing:
        raise GitError(f"Operation is missing rollback data: {', '.join(missing)}")
    if record.operation != "add-docstring":
        raise GitError("Only add-docstring rollback is supported")
    if record.status not in {"applied", "tested", "failed"}:
        raise GitError(f"Operation status is not rollback-compatible: {record.status}")


def rollback_last(db_path: Path, *, dry_run: bool = False) -> RollbackResult:
    if db_path is None:
        raise GitError("Rollback requires --db")

    record = read_last_add_docstring_operation(db_path)
    _require_record_fields(record)

    file_path = Path(record.file_path).resolve()
    if not file_path.exists():
        raise GitError("Rollback target file does not exist")

    project_root = Path(record.project_path).resolve()
    context = ensure_clean_git_repo(project_root)
    if not is_within_root(file_path, context.root):
        raise GitError("Rollback target file is outside the authorized project root")

    current_sha = sha256_file(file_path)
    if current_sha != record.after_sha256:
        raise GitError("Current file hash does not match the logged after_sha256")

    source_bytes = file_path.read_bytes()
    source, bom, encoding = _decode_python_bytes(source_bytes)
    module = cst.parse_module(source)
    remover = _DocstringRemover(record.symbol or "")
    updated_module = module.visit(remover)
    if not remover.matched:
        raise GitError("Rollback target symbol was not modified")

    restored_source = updated_module.code
    restored_bytes = _select_restored_bytes(
        source_bytes,
        restored_source,
        current_bom=bom,
        encoding=encoding,
        expected_sha256=record.before_sha256 or "",
    )
    candidate_sha = _sha256_bytes(restored_bytes)
    preview_diff_text = _preview_diff(file_path, source, restored_source)

    if dry_run:
        restored_sha = current_sha
        status = "planned"
        message = "Planned rollback of add-docstring operation."
    else:
        restored_sha = candidate_sha
        file_path.write_bytes(restored_bytes)
        status = "rolled_back"
        message = "Rolled back add-docstring operation."
        rollback_record = OperationRecord(
            created_at=now_utc_iso(),
            project_path=str(context.root),
            file_path=str(file_path),
            operation="rollback",
            symbol=record.symbol,
            before_sha256=current_sha,
            after_sha256=restored_sha,
            git_diff=preview_diff_text,
            pytest_command=None,
            pytest_exit_code=None,
            pytest_status=None,
            status=status,
            message=message,
        )
        write_last_operation(rollback_record)
        insert_record(db_path, rollback_record)

    return RollbackResult(
        db_path=db_path,
        project_root=context.root,
        file_path=file_path,
        symbol=record.symbol or "",
        dry_run=dry_run,
        before_sha256=current_sha,
        after_sha256=restored_sha,
        preview_diff_text=preview_diff_text,
        status=status,
        message=message,
    )
