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
    read_operation_by_id,
    read_rollback_for_source_operation,
    read_last_supported_operation,
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
    selector_type: str
    selector_value: int | str
    before_sha256: str
    after_sha256: str
    preview_diff_text: str
    status: str
    message: str
    source_operation: str
    source_operation_id: int | None
    rollback_operation_id: int | None
    written: bool
    logged: bool
    bytes_equal: bool
    exit_code: int

    @property
    def byte_exact(self) -> bool:
        return self.bytes_equal


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
    raise GitError("Rollback result does not match logged before_sha256", code="LEGACY_UNVERIFIABLE")


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
            raise GitError("Target function body is empty", code="LEGACY_UNVERIFIABLE")

        first_stmt = body[0]
        if not (
            isinstance(first_stmt, cst.SimpleStatementLine)
            and len(first_stmt.body) == 1
            and isinstance(first_stmt.body[0], cst.Expr)
            and isinstance(first_stmt.body[0].value, cst.SimpleString)
            and first_stmt.body[0].value.value == TODO_DOCSTRING
        ):
            raise GitError(
                "Target does not contain the SurePython skeleton docstring",
                code="LEGACY_UNVERIFIABLE",
            )

        self.matched = True
        return updated_node.with_changes(
            body=updated_node.body.with_changes(body=body[1:])
        )


class _ReturnTypeRemover(cst.CSTTransformer):
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
        if updated_node.returns is None:
            raise GitError("Target does not contain a return annotation", code="LEGACY_UNVERIFIABLE")
        self.matched = True
        return updated_node.with_changes(returns=None)


def _require_record_fields(record: OperationRecord) -> None:
    missing = [
        name
        for name in ("file_path", "operation", "symbol", "before_sha256", "after_sha256")
        if not getattr(record, name)
    ]
    if missing:
        raise GitError(
            f"Operation is missing rollback data: {', '.join(missing)}",
            code="ROLLBACK_NOT_AVAILABLE",
        )
    if record.operation not in {"add-docstring", "add-return-type"}:
        raise GitError(
            f"Operation is not rollback-compatible: {record.operation}",
            code="UNKNOWN_SQLITE_OPERATION",
        )
    if record.status not in {"applied", "tested", "failed"}:
        raise GitError(
            f"Operation status is not rollback-compatible: {record.status}",
            code="ROLLBACK_NOT_AVAILABLE",
        )


def _prepare_rollback_record(
    record: OperationRecord,
    *,
    db_path: Path,
    dry_run: bool,
    current_root: Path | None,
    selector_type: str,
    selector_value: int | str,
) -> tuple[RollbackResult, bytes | None]:
    if record.operation == "rollback":
        raise GitError("Rollback records cannot be rolled back again", code="ROLLBACK_RECORD_NOT_ALLOWED")

    _require_record_fields(record)
    if record.operation not in {"add-docstring", "add-return-type"}:
        raise GitError(
            f"Operation is not rollback-compatible: {record.operation}",
            code="UNKNOWN_SQLITE_OPERATION",
        )

    file_path = Path(record.file_path).resolve()
    if not file_path.exists():
        raise GitError("Rollback target file does not exist", code="FILE_NOT_FOUND")

    project_root = Path(record.project_path).resolve()
    active_root = (current_root or project_root).resolve()
    if current_root is not None and active_root != project_root:
        raise GitError("Operation belongs to a different project", code="PROJECT_MISMATCH")

    context = ensure_clean_git_repo(active_root)
    if not is_within_root(file_path, context.root):
        raise GitError(
            "Rollback target file is outside the authorized project root",
            code="FILE_OUTSIDE_PROJECT",
        )

    source_operation = read_rollback_for_source_operation(db_path, record.operation_id or -1)
    if source_operation is not None:
        raise GitError("Operation has already been rolled back", code="ROLLBACK_ALREADY_APPLIED")

    current_sha = sha256_file(file_path)
    if current_sha != record.after_sha256:
        raise GitError("Current file hash does not match the logged after_sha256", code="HASH_MISMATCH")

    source_bytes = file_path.read_bytes()
    source, bom, encoding = _decode_python_bytes(source_bytes)
    module = cst.parse_module(source)
    if record.operation == "add-docstring":
        remover = _DocstringRemover(record.symbol or "")
        operation_label = "add-docstring"
    else:
        remover = _ReturnTypeRemover(record.symbol or "")
        operation_label = "add-return-type"
    updated_module = module.visit(remover)
    if not remover.matched:
        raise GitError("Rollback target symbol was not modified", code="LEGACY_UNVERIFIABLE")

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
    bytes_equal = candidate_sha == record.before_sha256
    if not bytes_equal:
        raise GitError("Rollback result does not match logged before_sha256", code="LEGACY_UNVERIFIABLE")

    status = "preview" if dry_run else "rolled_back"
    message = (
        f"Planned rollback of {operation_label} operation {record.operation_id}."
        if dry_run
        else f"Rolled back {operation_label} operation {record.operation_id}."
    )
    rollback_operation_id: int | None = None
    restored_sha = current_sha if dry_run else candidate_sha

    if not dry_run:
        file_path.write_bytes(restored_bytes)
        rollback_record = OperationRecord(
            operation_id=None,
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
            source_operation_id=record.operation_id,
        )
        write_last_operation(rollback_record)
        rollback_operation_id = insert_record(db_path, rollback_record)
        write_last_operation(
            OperationRecord(
                operation_id=rollback_operation_id,
                created_at=rollback_record.created_at,
                project_path=rollback_record.project_path,
                file_path=rollback_record.file_path,
                operation=rollback_record.operation,
                symbol=rollback_record.symbol,
                before_sha256=rollback_record.before_sha256,
                after_sha256=rollback_record.after_sha256,
                git_diff=rollback_record.git_diff,
                pytest_command=rollback_record.pytest_command,
                pytest_exit_code=rollback_record.pytest_exit_code,
                pytest_status=rollback_record.pytest_status,
                status=rollback_record.status,
                message=rollback_record.message,
                source_operation_id=rollback_record.source_operation_id,
            )
        )

    result = RollbackResult(
        db_path=db_path,
        project_root=context.root,
        file_path=file_path,
        symbol=record.symbol or "",
        dry_run=dry_run,
        selector_type=selector_type,
        selector_value=selector_value,
        before_sha256=current_sha,
        after_sha256=restored_sha,
        preview_diff_text=preview_diff_text,
        status=status,
        message=message,
        source_operation=record.operation or "",
        source_operation_id=record.operation_id,
        rollback_operation_id=rollback_operation_id,
        written=not dry_run,
        logged=rollback_operation_id is not None,
        bytes_equal=bytes_equal,
        exit_code=0,
    )
    return result, restored_bytes


def rollback_by_id(
    db_path: Path,
    operation_id: int,
    *,
    dry_run: bool = False,
    current_root: Path | None = None,
) -> RollbackResult:
    if operation_id <= 0:
        raise GitError("Operation id must be positive", code="OPERATION_ID_INVALID")
    if db_path is None:
        raise GitError("Rollback requires --db", code="ROLLBACK_NOT_AVAILABLE")
    if not db_path.exists():
        raise GitError(f"Database does not exist: {db_path}", code="ROLLBACK_NOT_AVAILABLE")

    try:
        record = read_operation_by_id(db_path, operation_id)
    except FileNotFoundError as exc:
        raise GitError(str(exc), code="OPERATION_NOT_FOUND") from exc
    result, _ = _prepare_rollback_record(
        record,
        db_path=db_path,
        dry_run=dry_run,
        current_root=current_root,
        selector_type="operation_id",
        selector_value=operation_id,
    )
    return result


def rollback_last(
    db_path: Path,
    *,
    dry_run: bool = False,
    current_root: Path | None = None,
) -> RollbackResult:
    if db_path is None:
        raise GitError("Rollback requires --db", code="ROLLBACK_NOT_AVAILABLE")

    record = read_last_supported_operation(db_path)
    result, _ = _prepare_rollback_record(
        record,
        db_path=db_path,
        dry_run=dry_run,
        current_root=current_root,
        selector_type="last",
        selector_value="last",
    )
    return result
