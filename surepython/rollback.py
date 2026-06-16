from __future__ import annotations

import difflib
import hashlib
from dataclasses import dataclass
from pathlib import Path

import libcst as cst

from .codemods import TODO_DOCSTRING, _DecoratorInserter, _ParameterTypeInserter, _ReturnTypeInserter
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
    import_binding: str | None
    import_match_count: int | None
    expected_import_statement: str | None
    removed_import_statement: str | None
    parameter: str | None
    parameter_kind: str | None
    parameter_annotation: str | None
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
    return_annotation: str | None
    target_kind: str | None
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
    needle_text: str,
) -> list[bytes]:
    lines = _split_lines_keepends(source_bytes)
    candidates: list[bytes] = []
    encoded_needle = needle_text.encode(encoding)

    for index, line in enumerate(lines):
        if encoded_needle not in line:
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
    needle_text: str,
) -> bytes:
    for candidate in _byte_line_removal_candidates(
        source_bytes,
        restored_source,
        bom=current_bom,
        encoding=encoding,
        needle_text=needle_text,
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


class _ParameterTypeRemover(cst.CSTTransformer):
    def __init__(self, target_qname: str, parameter_name: str) -> None:
        self.target_qname = target_qname
        self.parameter_name = parameter_name
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

        params = updated_node.params
        replaced = False

        def update_params(values: tuple[cst.Param, ...]) -> tuple[cst.Param, ...]:
            nonlocal replaced
            updated_values = []
            for param in values:
                if param.name.value != self.parameter_name:
                    updated_values.append(param)
                    continue
                if param.annotation is None:
                    raise GitError(
                        "Target parameter does not contain an annotation",
                        code="LEGACY_UNVERIFIABLE",
                    )
                replaced = True
                updated_values.append(param.with_changes(annotation=None))
            return tuple(updated_values)

        posonly_params = update_params(tuple(params.posonly_params))
        regular_params = update_params(tuple(params.params))
        kwonly_params = update_params(tuple(params.kwonly_params))

        if params.star_arg is not cst.MaybeSentinel.DEFAULT and params.star_arg is not None:
            star_arg = params.star_arg
            if isinstance(star_arg, cst.Param) and star_arg.name.value == self.parameter_name:
                raise GitError(
                    "Variadic positional parameters are not supported",
                    code="PARAMETER_KIND_UNSUPPORTED",
                    details={"parameter": self.parameter_name, "kind": "var-positional"},
                )
        if params.star_kwarg is not None and params.star_kwarg.name.value == self.parameter_name:
            raise GitError(
                "Variadic keyword parameters are not supported",
                code="PARAMETER_KIND_UNSUPPORTED",
                details={"parameter": self.parameter_name, "kind": "var-keyword"},
            )

        if not replaced:
            raise GitError(
                "Target parameter not found",
                code="PARAMETER_NOT_FOUND",
                details={"parameter": self.parameter_name},
            )

        self.matched = True
        return updated_node.with_changes(
            params=updated_node.params.with_changes(
                posonly_params=posonly_params,
                params=regular_params,
                kwonly_params=kwonly_params,
            )
        )


def _remove_import_statement(module: cst.Module, record: OperationRecord) -> tuple[cst.Module, bool]:
    updated_body = []
    matched = False
    for stmt in module.body:
        if (
            not matched
            and isinstance(stmt, cst.SimpleStatementLine)
            and len(stmt.body) == 1
            and isinstance(stmt.body[0], (cst.Import, cst.ImportFrom))
        ):
            statement_code = module.code_for_node(stmt).strip()
            if statement_code == (record.import_statement or ""):
                matched = True
                continue
        updated_body.append(stmt)
    return module.with_changes(body=tuple(updated_body)), matched


def _restore_removed_import_bytes(source_bytes: bytes, removed_bytes: bytes, *, expected_sha256: str) -> bytes:
    bom = b"\xef\xbb\xbf" if source_bytes.startswith(b"\xef\xbb\xbf") else b""
    body = source_bytes[len(bom) :]
    lines = body.splitlines(keepends=True)
    candidates: list[bytes] = []
    for index in range(len(lines) + 1):
        candidate = bom + b"".join([*lines[:index], removed_bytes, *lines[index:]])
        if _sha256_bytes(candidate) == expected_sha256 and candidate not in candidates:
            candidates.append(candidate)
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise GitError("Rollback result does not match logged before_sha256", code="LEGACY_UNVERIFIABLE")
    raise GitError("Rollback result is ambiguous for the recorded import removal", code="LEGACY_UNVERIFIABLE")


def _remove_decorator(module: cst.Module, record: OperationRecord) -> tuple[cst.Module, bool]:
    target_qname = record.symbol or ""
    target_decorator = record.decorator_expression or ""
    target_position = record.decorator_position or "outermost"

    class _DecoratorRemover(cst.CSTTransformer):
        def __init__(self) -> None:
            self.scope: list[str] = []
            self.function_stack: list[bool] = []
            self.class_stack: list[bool] = []
            self.matched = False

        def visit_ClassDef(self, node: cst.ClassDef) -> None:
            self.scope.append(node.name.value)
            self.class_stack.append(".".join(self.scope) == target_qname)

        def leave_ClassDef(
            self, original_node: cst.ClassDef, updated_node: cst.ClassDef
        ) -> cst.CSTNode:
            is_target = self.class_stack.pop()
            self.scope.pop()
            if not is_target:
                return updated_node
            decorators = list(updated_node.decorators)
            index = 0 if target_position == "outermost" else len(decorators) - 1
            if 0 <= index < len(decorators):
                decorator = decorators[index]
                if module.code_for_node(decorator.decorator).strip() == target_decorator:
                    del decorators[index]
                    self.matched = True
            return updated_node.with_changes(decorators=tuple(decorators))

        def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
            self.scope.append(node.name.value)
            self.function_stack.append(".".join(self.scope) == target_qname)

        def leave_FunctionDef(
            self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
        ) -> cst.CSTNode:
            is_target = self.function_stack.pop()
            self.scope.pop()
            if not is_target:
                return updated_node
            decorators = list(updated_node.decorators)
            index = 0 if target_position == "outermost" else len(decorators) - 1
            if 0 <= index < len(decorators):
                decorator = decorators[index]
                if module.code_for_node(decorator.decorator).strip() == target_decorator:
                    del decorators[index]
                    self.matched = True
            return updated_node.with_changes(decorators=tuple(decorators))

    remover = _DecoratorRemover()
    updated_module = module.visit(remover)
    return updated_module, remover.matched


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
    if record.operation == "add-parameter-type" and not record.parameter:
        raise GitError(
            "Operation is missing rollback data: parameter",
            code="ROLLBACK_NOT_AVAILABLE",
        )
    if record.operation == "remove-parameter-type" and not record.parameter:
        raise GitError(
            "Operation is missing rollback data: parameter",
            code="ROLLBACK_NOT_AVAILABLE",
        )
    if record.operation == "remove-parameter-type" and not record.parameter_annotation:
        raise GitError(
            "Operation is missing rollback data: parameter_annotation",
            code="ROLLBACK_NOT_AVAILABLE",
        )
    if record.operation == "remove-return-type" and not record.return_annotation:
        raise GitError(
            "Operation is missing rollback data: return_annotation",
            code="ROLLBACK_NOT_AVAILABLE",
        )
    if record.operation == "add-import" and not record.import_statement:
        raise GitError(
            "Operation is missing rollback data: import_statement",
            code="ROLLBACK_NOT_AVAILABLE",
        )
    if record.operation == "add-import" and not record.import_binding:
        raise GitError(
            "Operation is missing rollback data: import_binding",
            code="ROLLBACK_NOT_AVAILABLE",
        )
    if record.operation == "remove-import" and not record.expected_import_statement:
        raise GitError(
            "Operation is missing rollback data: expected_import_statement",
            code="ROLLBACK_NOT_AVAILABLE",
        )
    if record.operation == "remove-import" and not record.removed_import_statement:
        raise GitError(
            "Operation is missing rollback data: removed_import_statement",
            code="ROLLBACK_NOT_AVAILABLE",
        )
    if record.operation == "remove-import" and record.import_match_count is None:
        raise GitError(
            "Operation is missing rollback data: import_match_count",
            code="ROLLBACK_NOT_AVAILABLE",
        )
    if record.operation == "remove-decorator" and not record.decorator_expression:
        raise GitError(
            "Operation is missing rollback data: decorator_expression",
            code="ROLLBACK_NOT_AVAILABLE",
        )
    if record.operation == "remove-decorator" and not record.decorator_position:
        raise GitError(
            "Operation is missing rollback data: decorator_position",
            code="ROLLBACK_NOT_AVAILABLE",
        )
    if record.operation == "remove-decorator" and not record.decorator_target_kind:
        raise GitError(
            "Operation is missing rollback data: decorator_target_kind",
            code="ROLLBACK_NOT_AVAILABLE",
        )
    if record.operation == "add-decorator" and not record.decorator_expression:
        raise GitError(
            "Operation is missing rollback data: decorator_expression",
            code="ROLLBACK_NOT_AVAILABLE",
        )
    if record.operation == "add-decorator" and not record.decorator_position:
        raise GitError(
            "Operation is missing rollback data: decorator_position",
            code="ROLLBACK_NOT_AVAILABLE",
        )
    if record.operation == "add-decorator" and not record.decorator_target_kind:
        raise GitError(
            "Operation is missing rollback data: decorator_target_kind",
            code="ROLLBACK_NOT_AVAILABLE",
        )
    if record.operation not in {"add-docstring", "add-return-type", "remove-return-type", "add-parameter-type", "remove-parameter-type", "add-import", "remove-import", "add-decorator", "remove-decorator"}:
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
        updated_module = module.visit(remover)
        if not remover.matched:
            raise GitError("Rollback target symbol was not modified", code="LEGACY_UNVERIFIABLE")
    elif record.operation == "add-return-type":
        remover = _ReturnTypeRemover(record.symbol or "")
        operation_label = "add-return-type"
        updated_module = module.visit(remover)
        if not remover.matched:
            raise GitError("Rollback target symbol was not modified", code="LEGACY_UNVERIFIABLE")
    elif record.operation == "remove-return-type":
        inserter = _ReturnTypeInserter(record.symbol or "", record.return_annotation or "")
        operation_label = "remove-return-type"
        updated_module = module.visit(inserter)
        if not inserter.matched:
            raise GitError("Rollback target symbol was not modified", code="LEGACY_UNVERIFIABLE")
    elif record.operation == "remove-parameter-type":
        inserter = _ParameterTypeInserter(record.symbol or "", record.parameter or "", record.parameter_annotation or "")
        operation_label = "remove-parameter-type"
        updated_module = module.visit(inserter)
        if not inserter.matched:
            raise GitError("Rollback target symbol was not modified", code="LEGACY_UNVERIFIABLE")
    elif record.operation == "add-parameter-type":
        remover = _ParameterTypeRemover(record.symbol or "", record.parameter or "")
        operation_label = "add-parameter-type"
        updated_module = module.visit(remover)
        if not remover.matched:
            raise GitError("Rollback target symbol was not modified", code="LEGACY_UNVERIFIABLE")
    elif record.operation == "add-decorator":
        updated_module, matched = _remove_decorator(module, record)
        operation_label = "add-decorator"
        if not matched:
            raise GitError("Rollback target symbol was not modified", code="LEGACY_UNVERIFIABLE")
    elif record.operation == "remove-decorator":
        inserter = _DecoratorInserter(
            record.symbol or "",
            cst.parse_expression(record.decorator_expression or ""),
            record.decorator_position or "outermost",
        )
        operation_label = "remove-decorator"
        updated_module = module.visit(inserter)
        if not inserter.matched:
            raise GitError("Rollback target symbol was not modified", code="LEGACY_UNVERIFIABLE")
    elif record.operation == "add-import":
        updated_module, matched = _remove_import_statement(module, record)
        operation_label = "add-import"
        if not matched:
            raise GitError("Rollback target import was not modified", code="LEGACY_UNVERIFIABLE")
    else:
        operation_label = "remove-import"
        removed_bytes = (record.removed_import_statement or "").encode("utf-8")
        restored_bytes = _restore_removed_import_bytes(
            source_bytes,
            removed_bytes,
            expected_sha256=record.before_sha256 or "",
        )
        restored_source, _, _ = _decode_python_bytes(restored_bytes)
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
        rollback_operation_id = None
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
                import_statement=record.import_statement,
                import_binding=record.import_binding,
                decorator_expression=record.decorator_expression,
                decorator_position=record.decorator_position,
                decorator_target_kind=record.decorator_target_kind,
                parameter=record.parameter,
                parameter_kind=record.parameter_kind,
                parameter_annotation=record.parameter_annotation,
                expected_return_annotation=record.expected_return_annotation,
                return_annotation=record.return_annotation,
                target_kind=record.target_kind,
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
                    import_statement=rollback_record.import_statement,
                    import_binding=rollback_record.import_binding,
                    decorator_expression=rollback_record.decorator_expression,
                    decorator_position=rollback_record.decorator_position,
                    decorator_target_kind=rollback_record.decorator_target_kind,
                    parameter=rollback_record.parameter,
                    parameter_kind=rollback_record.parameter_kind,
                    parameter_annotation=rollback_record.parameter_annotation,
                    expected_return_annotation=rollback_record.expected_return_annotation,
                    return_annotation=rollback_record.return_annotation,
                    target_kind=rollback_record.target_kind,
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
            import_binding=record.import_binding,
            import_match_count=record.import_match_count,
            expected_import_statement=record.expected_import_statement,
            removed_import_statement=record.removed_import_statement,
            parameter=record.parameter,
            parameter_kind=record.parameter_kind,
            parameter_annotation=record.parameter_annotation,
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
            return_annotation=record.return_annotation,
            target_kind=record.target_kind,
            written=not dry_run,
            logged=rollback_operation_id is not None,
            bytes_equal=bytes_equal,
            exit_code=0,
        )
        return result, restored_bytes

    restored_source = updated_module.code
    needle_text = (
        record.import_statement
        or record.decorator_expression
        or record.return_annotation
        or record.parameter_annotation
        or TODO_DOCSTRING
    )
    restored_bytes = _select_restored_bytes(
        source_bytes,
        restored_source,
        current_bom=bom,
        encoding=encoding,
        expected_sha256=record.before_sha256 or "",
        needle_text=needle_text,
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
            import_statement=record.import_statement,
            import_binding=record.import_binding,
            decorator_expression=record.decorator_expression,
            decorator_position=record.decorator_position,
            decorator_target_kind=record.decorator_target_kind,
            parameter=record.parameter,
            parameter_kind=record.parameter_kind,
            parameter_annotation=record.parameter_annotation,
            expected_return_annotation=record.expected_return_annotation,
            return_annotation=record.return_annotation,
            target_kind=record.target_kind,
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
                import_statement=rollback_record.import_statement,
                import_binding=rollback_record.import_binding,
                decorator_expression=rollback_record.decorator_expression,
                decorator_position=rollback_record.decorator_position,
                decorator_target_kind=rollback_record.decorator_target_kind,
                parameter=rollback_record.parameter,
                parameter_kind=rollback_record.parameter_kind,
                parameter_annotation=rollback_record.parameter_annotation,
                expected_return_annotation=rollback_record.expected_return_annotation,
                return_annotation=rollback_record.return_annotation,
                target_kind=rollback_record.target_kind,
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
        import_binding=record.import_binding,
        import_match_count=record.import_match_count,
        expected_import_statement=record.expected_import_statement,
        removed_import_statement=record.removed_import_statement,
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
        return_annotation=record.return_annotation,
        parameter=record.parameter,
        parameter_kind=record.parameter_kind,
        parameter_annotation=record.parameter_annotation,
        target_kind=record.target_kind,
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
