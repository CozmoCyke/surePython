from __future__ import annotations

import ast
import difflib
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path

import libcst as cst

from .datasette_log import (
    OperationRecord,
    insert_record,
    now_utc_iso,
    write_last_operation,
)
from .git_tools import (
    GitError,
    ensure_clean_git_repo,
    git_diff,
    is_within_root,
    sha256_file,
)
from .scanner import scan_file


TODO_DOCSTRING = '"""TODO: Document this function."""'


@dataclass(frozen=True)
class AddDocstringResult:
    file_path: Path
    project_root: Path
    db_path: Path | None
    symbol: str
    before_sha256: str
    after_sha256: str
    preview_diff_text: str | None
    git_stat: str
    git_diff_text: str
    pytest_command: str | None
    pytest_exit_code: int | None
    pytest_status: str | None
    status: str
    message: str
    operation_id: int | None
    logged: bool
    rollback_available: bool
    exit_code: int


@dataclass(frozen=True)
class AddReturnTypeResult:
    file_path: Path
    project_root: Path
    db_path: Path | None
    symbol: str
    annotation: str
    before_sha256: str
    after_sha256: str
    preview_diff_text: str | None
    git_stat: str
    git_diff_text: str
    pytest_command: str | None
    pytest_exit_code: int | None
    pytest_status: str | None
    status: str
    message: str
    operation_id: int | None
    logged: bool
    rollback_available: bool
    exit_code: int


@dataclass(frozen=True)
class AddParameterTypeResult:
    file_path: Path
    project_root: Path
    db_path: Path | None
    symbol: str
    parameter: str
    annotation: str
    before_sha256: str
    after_sha256: str
    preview_diff_text: str | None
    git_stat: str
    git_diff_text: str
    pytest_command: str | None
    pytest_exit_code: int | None
    pytest_status: str | None
    status: str
    message: str
    operation_id: int | None
    logged: bool
    rollback_available: bool
    exit_code: int


def _has_docstring(node: ast.AST) -> bool:
    return ast.get_docstring(node) is not None


def _find_target_node(module: ast.Module, target_qname: str) -> ast.AST | None:
    def walk(nodes: list[ast.AST], prefix: list[str]) -> ast.AST | None:
        for node in nodes:
            if isinstance(node, ast.ClassDef):
                qname = ".".join([*prefix, node.name])
                if qname == target_qname:
                    return node
                found = walk(node.body, [*prefix, node.name])
                if found is not None:
                    return found
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qname = ".".join([*prefix, node.name])
                if qname == target_qname:
                    return node
        return None

    return walk(module.body, [])


def _resolve_target(records, target: str) -> str:
    if "." in target:
        matches = [
            record
            for record in records
            if record.qualified_name == target and record.type in {"function", "method"}
        ]
    else:
        matches = [
            record
            for record in records
            if record.qualified_name.split(".")[-1] == target
            and record.type in {"function", "method"}
        ]
    if not matches:
        raise GitError("Target symbol not found", code="TARGET_NOT_FOUND")
    if len(matches) > 1:
        raise GitError("Target symbol is ambiguous", code="TARGET_AMBIGUOUS")
    return matches[0].qualified_name


def _decode_python_bytes(data: bytes) -> tuple[str, bytes, str]:
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8"), b"\xef\xbb\xbf", "utf-8"
    return data.decode("utf-8"), b"", "utf-8"


def _encode_python_text(text: str, bom: bytes, encoding: str) -> bytes:
    return bom + text.encode(encoding)


def _validate_annotation_expression(annotation: str, *, empty_code: str) -> cst.BaseExpression:
    if not annotation.strip():
        raise GitError("Annotation is empty", code=empty_code)
    try:
        expression = cst.parse_expression(annotation)
        ast.parse(f"def _surepython_probe() -> {annotation}:\n    pass\n")
    except Exception as exc:
        raise GitError(f"Annotation is invalid: {annotation}", code="ANNOTATION_INVALID", details={"annotation": annotation}) from exc
    return expression


def _validate_return_annotation(annotation: str) -> cst.BaseExpression:
    return _validate_annotation_expression(annotation, empty_code="ANNOTATION_REQUIRED")


def _validate_parameter_annotation(annotation: str) -> cst.BaseExpression:
    return _validate_annotation_expression(annotation, empty_code="ANNOTATION_REQUIRED")


def _resolve_parameter_kind(node: ast.AST, parameter_name: str) -> tuple[str, ast.arg]:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        arguments = node.args
        for param in arguments.posonlyargs:
            if param.arg == parameter_name:
                return "positional-only", param
        for param in arguments.args:
            if param.arg == parameter_name:
                return "positional-or-keyword", param
        for param in arguments.kwonlyargs:
            if param.arg == parameter_name:
                return "keyword-only", param
        if arguments.vararg is not None and arguments.vararg.arg == parameter_name:
            raise GitError(
                "Variadic positional parameters are not supported",
                code="PARAMETER_KIND_UNSUPPORTED",
                details={"parameter": parameter_name, "kind": "var-positional"},
            )
        if arguments.kwarg is not None and arguments.kwarg.arg == parameter_name:
            raise GitError(
                "Variadic keyword parameters are not supported",
                code="PARAMETER_KIND_UNSUPPORTED",
                details={"parameter": parameter_name, "kind": "var-keyword"},
            )
    raise GitError(
        "Target parameter not found",
        code="PARAMETER_NOT_FOUND",
        details={"parameter": parameter_name},
    )


def run_pytest(cwd: Path, command: str | None = None) -> tuple[int, str]:
    if command is None:
        completed = subprocess.run(
            [sys.executable, "-m", "pytest"],
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
        )
    else:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            shell=True,
            check=False,
            capture_output=True,
            text=True,
        )
    output = (completed.stdout or "") + (completed.stderr or "")
    return completed.returncode, output.strip()


def _preview_diff(file_path: Path, before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=str(file_path),
            tofile=str(file_path),
        )
    ).rstrip("\n")


def _write_state(
    *,
    project_root: Path,
    file_path: Path,
    db_path: Path | None,
    operation: str,
    symbol: str | None,
    parameter: str | None = None,
    before_sha256: str | None,
    after_sha256: str | None,
    git_diff_text: str | None,
    pytest_command: str | None,
    pytest_exit_code: int | None,
    pytest_status: str | None,
    status: str,
    message: str | None,
) -> int | None:
    record = OperationRecord(
        created_at=now_utc_iso(),
        project_path=str(project_root),
        file_path=str(file_path),
        operation=operation,
        symbol=symbol,
        parameter=parameter,
        before_sha256=before_sha256,
        after_sha256=after_sha256,
        git_diff=git_diff_text,
        pytest_command=pytest_command,
        pytest_exit_code=pytest_exit_code,
        pytest_status=pytest_status,
        status=status,
        message=message,
    )
    operation_id: int | None = None
    if db_path is not None and status not in {"planned", "refused"}:
        operation_id = insert_record(db_path, record)
    write_last_operation(replace(record, operation_id=operation_id))
    return operation_id


class _DocstringInserter(cst.CSTTransformer):
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
        is_target = qname == self.target_qname
        self.function_stack.append(is_target)
        if is_target:
            body = node.body.body
            if body:
                first_stmt = body[0]
                if (
                    isinstance(first_stmt, cst.SimpleStatementLine)
                    and len(first_stmt.body) == 1
                    and isinstance(first_stmt.body[0], cst.Expr)
                    and isinstance(first_stmt.body[0].value, cst.SimpleString)
                ):
                    raise GitError("Target already has a docstring", code="DOCSTRING_EXISTS")

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.CSTNode:
        is_target = self.function_stack.pop()
        if not is_target:
            return updated_node
        self.matched = True
        docstring_line = cst.SimpleStatementLine(
            [cst.Expr(cst.SimpleString(TODO_DOCSTRING))]
        )
        body = updated_node.body.with_changes(
            body=(docstring_line, *updated_node.body.body)
        )
        return updated_node.with_changes(body=body)


class _ReturnTypeInserter(cst.CSTTransformer):
    def __init__(self, target_qname: str, annotation: str) -> None:
        self.target_qname = target_qname
        self.annotation = annotation
        self.annotation_expression = _validate_return_annotation(annotation)
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
        is_target = qname == self.target_qname
        self.function_stack.append(is_target)
        if is_target and node.returns is not None:
            raise GitError("Target already has a return annotation", code="ANNOTATION_EXISTS")

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.CSTNode:
        is_target = self.function_stack.pop()
        if not is_target:
            return updated_node
        self.matched = True
        return updated_node.with_changes(
            returns=cst.Annotation(annotation=self.annotation_expression)
        )


class _ParameterTypeInserter(cst.CSTTransformer):
    def __init__(self, target_qname: str, parameter_name: str, annotation: str) -> None:
        self.target_qname = target_qname
        self.parameter_name = parameter_name
        self.annotation = annotation
        self.annotation_expression = _validate_parameter_annotation(annotation)
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
                if param.annotation is not None:
                    raise GitError(
                        "Target parameter already has an annotation",
                        code="PARAMETER_ANNOTATION_EXISTS",
                        details={
                            "symbol": self.target_qname,
                            "parameter": self.parameter_name,
                        },
                    )
                replaced = True
                updated_values.append(
                    param.with_changes(
                        annotation=cst.Annotation(annotation=self.annotation_expression)
                    )
                )
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


def add_docstring(
    file_path: Path,
    target: str,
    *,
    project_root: Path | None = None,
    db_path: Path | None = None,
    run_tests: bool = False,
    test_command: str | None = None,
    dry_run: bool = False,
) -> AddDocstringResult:
    file_path = file_path.resolve()
    if not file_path.exists():
        raise GitError("File does not exist", code="FILE_NOT_FOUND")

    context = ensure_clean_git_repo(project_root or file_path.parent)
    if not is_within_root(file_path, context.root):
        raise GitError("File is outside the authorized project root", code="FILE_OUTSIDE_PROJECT")

    records = scan_file(file_path)
    target_qname = _resolve_target(records, target)

    before_sha256 = sha256_file(file_path)
    source = file_path.read_text(encoding="utf-8")

    try:
        cst.parse_module(source)
    except Exception as exc:  # pragma: no cover - defensive
        _write_state(
            project_root=context.root,
            file_path=file_path,
            db_path=db_path,
            operation="add-docstring",
            symbol=target_qname,
            before_sha256=before_sha256,
            after_sha256=None,
            git_diff_text=None,
            pytest_command=None,
            pytest_exit_code=None,
            pytest_status=None,
            status="refused",
            message=f"LibCST parse failed: {exc}",
        )
        raise GitError(
            f"LibCST parse failed: {exc}",
            code="PARSE_ERROR",
            details={"file_path": str(file_path)},
        ) from exc

    module = ast.parse(source, filename=str(file_path))
    node = _find_target_node(module, target_qname)
    if node is None:
        _write_state(
            project_root=context.root,
            file_path=file_path,
            db_path=db_path,
            operation="add-docstring",
            symbol=target_qname,
            before_sha256=before_sha256,
            after_sha256=None,
            git_diff_text=None,
            pytest_command=None,
            pytest_exit_code=None,
            pytest_status=None,
            status="refused",
            message="Target symbol not found",
        )
        raise GitError("Target symbol not found", code="TARGET_NOT_FOUND")

    if _has_docstring(node):
        _write_state(
            project_root=context.root,
            file_path=file_path,
            db_path=db_path,
            operation="add-docstring",
            symbol=target_qname,
            before_sha256=before_sha256,
            after_sha256=None,
            git_diff_text=None,
            pytest_command=None,
            pytest_exit_code=None,
            pytest_status=None,
            status="refused",
            message="Target already has a docstring",
        )
        raise GitError("Target already has a docstring", code="DOCSTRING_EXISTS")

    cst_module = cst.parse_module(source)
    transformer = _DocstringInserter(target_qname)
    updated_module = cst_module.visit(transformer)
    if not transformer.matched:
        _write_state(
            project_root=context.root,
            file_path=file_path,
            db_path=db_path,
            operation="add-docstring",
            symbol=target_qname,
            before_sha256=before_sha256,
            after_sha256=None,
            git_diff_text=None,
            pytest_command=None,
            pytest_exit_code=None,
            pytest_status=None,
            status="refused",
            message="Target symbol not found",
        )
        raise GitError("Target symbol not found", code="TARGET_NOT_FOUND")

    updated_source = updated_module.code
    preview_diff_text = _preview_diff(file_path, source, updated_source)

    if dry_run:
        after_sha256 = before_sha256
    else:
        file_path.write_text(updated_source, encoding="utf-8")
        after_sha256 = sha256_file(file_path)

    stat, diff_text = git_diff(context.root) if not dry_run else ("", "")

    pytest_exit_code: int | None = None
    pytest_status: str | None = None
    pytest_command = None
    status = "planned" if dry_run else "applied"
    message = "Planned skeleton docstring." if dry_run else "Added skeleton docstring."

    if run_tests and not dry_run:
        pytest_command = test_command or f"{sys.executable} -m pytest"
        pytest_exit_code, pytest_output = run_pytest(context.root, test_command)
        pytest_status = "passed" if pytest_exit_code == 0 else "failed"
        if pytest_output:
            message = f"{message} Pytest output: {pytest_output}"
        status = "tested" if pytest_exit_code == 0 else "failed"

    operation_id: int | None = None
    if not dry_run:
        operation_id = _write_state(
            project_root=context.root,
            file_path=file_path,
            db_path=db_path,
            operation="add-docstring",
            symbol=target_qname,
            before_sha256=before_sha256,
            after_sha256=after_sha256,
            git_diff_text=diff_text,
            pytest_command=pytest_command,
            pytest_exit_code=pytest_exit_code,
            pytest_status=pytest_status,
            status=status,
            message=message,
        )
    elif db_path is not None:
        _write_state(
            project_root=context.root,
            file_path=file_path,
            db_path=db_path,
            operation="add-docstring",
            symbol=target_qname,
            before_sha256=before_sha256,
            after_sha256=after_sha256,
            git_diff_text=preview_diff_text,
            pytest_command=pytest_command,
            pytest_exit_code=pytest_exit_code,
            pytest_status=pytest_status,
            status=status,
            message=message,
        )

    logged = operation_id is not None
    return AddDocstringResult(
        file_path=file_path,
        project_root=context.root,
        db_path=db_path,
        symbol=target_qname,
        before_sha256=before_sha256,
        after_sha256=after_sha256,
        preview_diff_text=preview_diff_text if dry_run else None,
        git_stat=stat,
        git_diff_text=diff_text,
        pytest_command=pytest_command,
        pytest_exit_code=pytest_exit_code,
        pytest_status=pytest_status,
        status=status,
        message=message,
        operation_id=operation_id,
        logged=logged,
        rollback_available=logged,
        exit_code=0 if pytest_exit_code in (None, 0) else 3,
    )


def add_return_type(
    file_path: Path,
    target: str,
    annotation: str,
    *,
    project_root: Path | None = None,
    db_path: Path | None = None,
    run_tests: bool = False,
    test_command: str | None = None,
    dry_run: bool = False,
) -> AddReturnTypeResult:
    file_path = file_path.resolve()
    if not file_path.exists():
        raise GitError("File does not exist", code="FILE_NOT_FOUND")

    annotation_expression = _validate_return_annotation(annotation)
    context = ensure_clean_git_repo(project_root or file_path.parent)
    if not is_within_root(file_path, context.root):
        raise GitError("File is outside the authorized project root", code="FILE_OUTSIDE_PROJECT")

    records = scan_file(file_path)
    target_qname = _resolve_target(records, target)

    before_sha256 = sha256_file(file_path)
    source_bytes = file_path.read_bytes()
    source, bom, encoding = _decode_python_bytes(source_bytes)

    try:
        cst.parse_module(source)
    except Exception as exc:  # pragma: no cover - defensive
        _write_state(
            project_root=context.root,
            file_path=file_path,
            db_path=db_path,
            operation="add-return-type",
            symbol=target_qname,
            before_sha256=before_sha256,
            after_sha256=None,
            git_diff_text=None,
            pytest_command=None,
            pytest_exit_code=None,
            pytest_status=None,
            status="refused",
            message=f"LibCST parse failed: {exc}",
        )
        raise GitError(
            f"LibCST parse failed: {exc}",
            code="PARSE_ERROR",
            details={"file_path": str(file_path)},
        ) from exc

    module = ast.parse(source, filename=str(file_path))
    node = _find_target_node(module, target_qname)
    if node is None:
        _write_state(
            project_root=context.root,
            file_path=file_path,
            db_path=db_path,
            operation="add-return-type",
            symbol=target_qname,
            before_sha256=before_sha256,
            after_sha256=None,
            git_diff_text=None,
            pytest_command=None,
            pytest_exit_code=None,
            pytest_status=None,
            status="refused",
            message="Target symbol not found",
        )
        raise GitError("Target symbol not found", code="TARGET_NOT_FOUND")
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise GitError("Target is not a function or method", code="TARGET_UNSUPPORTED")
    if node.returns is not None:
        _write_state(
            project_root=context.root,
            file_path=file_path,
            db_path=db_path,
            operation="add-return-type",
            symbol=target_qname,
            before_sha256=before_sha256,
            after_sha256=None,
            git_diff_text=None,
            pytest_command=None,
            pytest_exit_code=None,
            pytest_status=None,
            status="refused",
            message="Target already has a return annotation",
        )
        raise GitError("Target already has a return annotation", code="ANNOTATION_EXISTS")

    cst_module = cst.parse_module(source)
    transformer = _ReturnTypeInserter(target_qname, annotation)
    transformer.annotation_expression = annotation_expression
    updated_module = cst_module.visit(transformer)
    if not transformer.matched:
        _write_state(
            project_root=context.root,
            file_path=file_path,
            db_path=db_path,
            operation="add-return-type",
            symbol=target_qname,
            before_sha256=before_sha256,
            after_sha256=None,
            git_diff_text=None,
            pytest_command=None,
            pytest_exit_code=None,
            pytest_status=None,
            status="refused",
            message="Target symbol not found",
        )
        raise GitError("Target symbol not found", code="TARGET_NOT_FOUND")

    updated_source = updated_module.code
    updated_bytes = _encode_python_text(updated_source, bom, encoding)
    preview_diff_text = _preview_diff(file_path, source, updated_source)

    if dry_run:
        after_sha256 = before_sha256
    else:
        file_path.write_bytes(updated_bytes)
        after_sha256 = sha256_file(file_path)

    stat, diff_text = git_diff(context.root) if not dry_run else ("", "")

    pytest_exit_code: int | None = None
    pytest_status: str | None = None
    pytest_command = None
    status = "planned" if dry_run else "applied"
    message = (
        f"Planned return annotation: {annotation}."
        if dry_run
        else f"Added return annotation: {annotation}."
    )

    if run_tests and not dry_run:
        pytest_command = test_command or f"{sys.executable} -m pytest"
        pytest_exit_code, pytest_output = run_pytest(context.root, test_command)
        pytest_status = "passed" if pytest_exit_code == 0 else "failed"
        if pytest_output:
            message = f"{message} Pytest output: {pytest_output}"
        status = "tested" if pytest_exit_code == 0 else "failed"

    operation_id: int | None = None
    if not dry_run:
        operation_id = _write_state(
            project_root=context.root,
            file_path=file_path,
            db_path=db_path,
            operation="add-return-type",
            symbol=target_qname,
            before_sha256=before_sha256,
            after_sha256=after_sha256,
            git_diff_text=diff_text,
            pytest_command=pytest_command,
            pytest_exit_code=pytest_exit_code,
            pytest_status=pytest_status,
            status=status,
            message=message,
        )
    elif db_path is not None:
        _write_state(
            project_root=context.root,
            file_path=file_path,
            db_path=db_path,
            operation="add-return-type",
            symbol=target_qname,
            before_sha256=before_sha256,
            after_sha256=after_sha256,
            git_diff_text=preview_diff_text,
            pytest_command=pytest_command,
            pytest_exit_code=pytest_exit_code,
            pytest_status=pytest_status,
            status=status,
            message=message,
        )

    logged = operation_id is not None
    return AddReturnTypeResult(
        file_path=file_path,
        project_root=context.root,
        db_path=db_path,
        symbol=target_qname,
        annotation=annotation,
        before_sha256=before_sha256,
        after_sha256=after_sha256,
        preview_diff_text=preview_diff_text if dry_run else None,
        git_stat=stat,
        git_diff_text=diff_text,
        pytest_command=pytest_command,
        pytest_exit_code=pytest_exit_code,
        pytest_status=pytest_status,
        status=status,
        message=message,
        operation_id=operation_id,
        logged=logged,
        rollback_available=logged,
        exit_code=0 if pytest_exit_code in (None, 0) else 3,
    )


def add_parameter_type(
    file_path: Path,
    target: str,
    parameter: str,
    annotation: str,
    *,
    project_root: Path | None = None,
    db_path: Path | None = None,
    run_tests: bool = False,
    test_command: str | None = None,
    dry_run: bool = False,
) -> AddParameterTypeResult:
    file_path = file_path.resolve()
    if not file_path.exists():
        raise GitError("File does not exist", code="FILE_NOT_FOUND")
    if not parameter.strip():
        raise GitError("Parameter name is empty", code="PARAMETER_REQUIRED")

    annotation_expression = _validate_parameter_annotation(annotation)
    context = ensure_clean_git_repo(project_root or file_path.parent)
    if not is_within_root(file_path, context.root):
        raise GitError("File is outside the authorized project root", code="FILE_OUTSIDE_PROJECT")

    records = scan_file(file_path)
    target_qname = _resolve_target(records, target)

    before_sha256 = sha256_file(file_path)
    source_bytes = file_path.read_bytes()
    source, bom, encoding = _decode_python_bytes(source_bytes)

    try:
        cst.parse_module(source)
    except Exception as exc:  # pragma: no cover - defensive
        _write_state(
            project_root=context.root,
            file_path=file_path,
            db_path=db_path,
            operation="add-parameter-type",
            symbol=target_qname,
            parameter=parameter,
            before_sha256=before_sha256,
            after_sha256=None,
            git_diff_text=None,
            pytest_command=None,
            pytest_exit_code=None,
            pytest_status=None,
            status="refused",
            message=f"LibCST parse failed: {exc}",
        )
        raise GitError(
            f"LibCST parse failed: {exc}",
            code="PARSE_ERROR",
            details={"file_path": str(file_path)},
        ) from exc

    module = ast.parse(source, filename=str(file_path))
    node = _find_target_node(module, target_qname)
    if node is None:
        _write_state(
            project_root=context.root,
            file_path=file_path,
            db_path=db_path,
            operation="add-parameter-type",
            symbol=target_qname,
            parameter=parameter,
            before_sha256=before_sha256,
            after_sha256=None,
            git_diff_text=None,
            pytest_command=None,
            pytest_exit_code=None,
            pytest_status=None,
            status="refused",
            message="Target symbol not found",
        )
        raise GitError("Target symbol not found", code="TARGET_NOT_FOUND")
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise GitError("Target is not a function or method", code="TARGET_UNSUPPORTED")

    _resolved_kind, resolved_param = _resolve_parameter_kind(node, parameter)
    if resolved_param.annotation is not None:
        _write_state(
            project_root=context.root,
            file_path=file_path,
            db_path=db_path,
            operation="add-parameter-type",
            symbol=target_qname,
            parameter=parameter,
            before_sha256=before_sha256,
            after_sha256=None,
            git_diff_text=None,
            pytest_command=None,
            pytest_exit_code=None,
            pytest_status=None,
            status="refused",
            message="Target parameter already has an annotation",
        )
        raise GitError(
            "Target parameter already has an annotation",
            code="PARAMETER_ANNOTATION_EXISTS",
            details={"symbol": target_qname, "parameter": parameter},
        )

    cst_module = cst.parse_module(source)
    transformer = _ParameterTypeInserter(target_qname, parameter, annotation)
    transformer.annotation_expression = annotation_expression
    updated_module = cst_module.visit(transformer)
    if not transformer.matched:
        _write_state(
            project_root=context.root,
            file_path=file_path,
            db_path=db_path,
            operation="add-parameter-type",
            symbol=target_qname,
            parameter=parameter,
            before_sha256=before_sha256,
            after_sha256=None,
            git_diff_text=None,
            pytest_command=None,
            pytest_exit_code=None,
            pytest_status=None,
            status="refused",
            message="Target parameter not found",
        )
        raise GitError(
            "Target parameter not found",
            code="PARAMETER_NOT_FOUND",
            details={"symbol": target_qname, "parameter": parameter},
        )

    updated_source = updated_module.code
    updated_bytes = _encode_python_text(updated_source, bom, encoding)
    preview_diff_text = _preview_diff(file_path, source, updated_source)

    if dry_run:
        after_sha256 = before_sha256
    else:
        file_path.write_bytes(updated_bytes)
        after_sha256 = sha256_file(file_path)

    stat, diff_text = git_diff(context.root) if not dry_run else ("", "")

    pytest_exit_code: int | None = None
    pytest_status: str | None = None
    pytest_command = None
    status = "planned" if dry_run else "applied"
    message = (
        f"Planned parameter annotation: {parameter}: {annotation}."
        if dry_run
        else f"Added parameter annotation: {parameter}: {annotation}."
    )

    if run_tests and not dry_run:
        pytest_command = test_command or f"{sys.executable} -m pytest"
        pytest_exit_code, pytest_output = run_pytest(context.root, test_command)
        pytest_status = "passed" if pytest_exit_code == 0 else "failed"
        if pytest_output:
            message = f"{message} Pytest output: {pytest_output}"
        status = "tested" if pytest_exit_code == 0 else "failed"

    operation_id: int | None = None
    if not dry_run:
        operation_id = _write_state(
            project_root=context.root,
            file_path=file_path,
            db_path=db_path,
            operation="add-parameter-type",
            symbol=target_qname,
            parameter=parameter,
            before_sha256=before_sha256,
            after_sha256=after_sha256,
            git_diff_text=diff_text,
            pytest_command=pytest_command,
            pytest_exit_code=pytest_exit_code,
            pytest_status=pytest_status,
            status=status,
            message=message,
        )
    elif db_path is not None:
        _write_state(
            project_root=context.root,
            file_path=file_path,
            db_path=db_path,
            operation="add-parameter-type",
            symbol=target_qname,
            parameter=parameter,
            before_sha256=before_sha256,
            after_sha256=after_sha256,
            git_diff_text=preview_diff_text,
            pytest_command=pytest_command,
            pytest_exit_code=pytest_exit_code,
            pytest_status=pytest_status,
            status=status,
            message=message,
        )

    logged = operation_id is not None
    return AddParameterTypeResult(
        file_path=file_path,
        project_root=context.root,
        db_path=db_path,
        symbol=target_qname,
        parameter=parameter,
        annotation=annotation,
        before_sha256=before_sha256,
        after_sha256=after_sha256,
        preview_diff_text=preview_diff_text if dry_run else None,
        git_stat=stat,
        git_diff_text=diff_text,
        pytest_command=pytest_command,
        pytest_exit_code=pytest_exit_code,
        pytest_status=pytest_status,
        status=status,
        message=message,
        operation_id=operation_id,
        logged=logged,
        rollback_available=logged,
        exit_code=0 if pytest_exit_code in (None, 0) else 3,
    )
