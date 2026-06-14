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
class RemoveReturnTypeResult:
    file_path: Path
    project_root: Path
    db_path: Path | None
    symbol: str
    expected_annotation: str
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


@dataclass(frozen=True)
class AddImportResult:
    file_path: Path
    project_root: Path
    db_path: Path | None
    symbol: str
    binding: str
    statement: str
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
class AddDecoratorResult:
    file_path: Path
    project_root: Path
    db_path: Path | None
    symbol: str
    target_kind: str
    decorator: str
    position: str
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


def _resolve_decorator_target(records, target: str):
    allowed_types = {"function", "method", "class"}
    if "." in target:
        matches = [
            record
            for record in records
            if record.qualified_name == target and record.type in allowed_types
        ]
    else:
        matches = [
            record
            for record in records
            if record.qualified_name.split(".")[-1] == target
            and record.type in allowed_types
        ]
    if not matches:
        raise GitError("Target symbol not found", code="TARGET_NOT_FOUND")
    if len(matches) > 1:
        raise GitError("Target symbol is ambiguous", code="TARGET_AMBIGUOUS")
    return matches[0]


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


def _validate_expected_return_annotation(annotation: str) -> cst.BaseExpression:
    try:
        return _validate_annotation_expression(annotation, empty_code="RETURN_ANNOTATION_REQUIRED")
    except GitError as exc:
        if exc.code == "ANNOTATION_INVALID":
            raise GitError(
                str(exc),
                code="RETURN_ANNOTATION_INVALID",
                details=exc.details,
            ) from exc
        raise


def _validate_parameter_annotation(annotation: str) -> cst.BaseExpression:
    return _validate_annotation_expression(annotation, empty_code="ANNOTATION_REQUIRED")


def _validate_decorator_expression(decorator: str) -> cst.BaseExpression:
    if not decorator.strip():
        raise GitError("Decorator expression is required", code="DECORATOR_REQUIRED")
    if decorator.lstrip().startswith("@"):
        raise GitError("Decorator expression is invalid", code="DECORATOR_INVALID")

    try:
        expression = cst.parse_expression(decorator)
        parsed = ast.parse(decorator, mode="eval").body
    except Exception as exc:
        raise GitError(
            f"Decorator expression is invalid: {decorator}",
            code="DECORATOR_INVALID",
            details={"decorator": decorator},
        ) from exc

    def validate(node: ast.AST) -> None:
        if isinstance(node, ast.Name):
            return
        if isinstance(node, ast.Constant):
            return
        if isinstance(node, ast.Attribute):
            validate(node.value)
            return
        if isinstance(node, ast.Call):
            if not isinstance(node.func, (ast.Name, ast.Attribute)):
                raise GitError(
                    f"Decorator expression is invalid: {decorator}",
                    code="DECORATOR_INVALID",
                    details={"decorator": decorator},
                )
            validate(node.func)
            for arg in node.args:
                if isinstance(arg, ast.Starred):
                    raise GitError(
                        f"Decorator expression is invalid: {decorator}",
                        code="DECORATOR_INVALID",
                        details={"decorator": decorator},
                    )
                validate(arg)
            for keyword in node.keywords:
                if keyword.arg is None:
                    raise GitError(
                        f"Decorator expression is invalid: {decorator}",
                        code="DECORATOR_INVALID",
                        details={"decorator": decorator},
                    )
                validate(keyword.value)
            return
        if isinstance(node, ast.List):
            for element in node.elts:
                validate(element)
            return
        if isinstance(node, ast.Tuple):
            for element in node.elts:
                validate(element)
            return
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if key is not None:
                    validate(key)
                validate(value)
            return
        raise GitError(
            f"Decorator expression is invalid: {decorator}",
            code="DECORATOR_INVALID",
            details={"decorator": decorator},
        )

    validate(parsed)
    return expression


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


@dataclass(frozen=True)
class _ImportSpec:
    kind: str
    module_name: str
    imported_name: str
    binding: str
    canonical_statement: str


def _leftmost_binding_name(node: cst.BaseExpression | cst.Attribute | cst.Name) -> str:
    if isinstance(node, cst.Name):
        return node.value
    if isinstance(node, cst.Attribute):
        return _leftmost_binding_name(node.value)
    raise GitError("Import statement is invalid", code="IMPORT_STATEMENT_INVALID")


def _module_code(module: cst.Module, node: cst.CSTNode | None) -> str:
    if node is None:
        return ""
    try:
        return module.code_for_node(node).strip()
    except Exception as exc:  # pragma: no cover - defensive
        raise GitError("Import statement is invalid", code="IMPORT_STATEMENT_INVALID") from exc


def _parse_import_statement(statement: str) -> tuple[_ImportSpec, cst.SimpleStatementLine]:
    if not statement.strip():
        raise GitError("Import statement is required", code="IMPORT_STATEMENT_REQUIRED")

    try:
        module = cst.parse_module(statement)
    except Exception as exc:
        raise GitError("Import statement is invalid", code="IMPORT_STATEMENT_INVALID") from exc

    if len(module.body) != 1 or not isinstance(module.body[0], cst.SimpleStatementLine):
        raise GitError("Import statement is invalid", code="IMPORT_STATEMENT_INVALID")
    statement_line = module.body[0]
    if len(statement_line.body) != 1:
        raise GitError("Multiple statements are not supported", code="IMPORT_STATEMENT_INVALID")

    node = statement_line.body[0]
    canonical_statement = module.code.strip()

    if isinstance(node, cst.Import):
        if len(node.names) != 1:
            raise GitError(
                "Multiple import bindings are not supported",
                code="IMPORT_MULTIPLE_BINDINGS_UNSUPPORTED",
            )
        alias = node.names[0]
        binding = alias.asname.name.value if alias.asname else _leftmost_binding_name(alias.name)
        module_name = _module_code(module, alias.name)
        return (
            _ImportSpec(
                kind="import",
                module_name=module_name,
                imported_name=module_name,
                binding=binding,
                canonical_statement=canonical_statement,
            ),
            statement_line,
        )

    if isinstance(node, cst.ImportFrom):
        relative = getattr(node, "relative", None)
        if relative:
            raise GitError("Relative imports are not supported", code="IMPORT_RELATIVE_UNSUPPORTED")
        if node.module is None:
            raise GitError("Relative imports are not supported", code="IMPORT_RELATIVE_UNSUPPORTED")
        if isinstance(node.names, cst.ImportStar):
            raise GitError("Wildcard imports are not supported", code="IMPORT_WILDCARD_UNSUPPORTED")
        if len(node.names) != 1:
            raise GitError(
                "Multiple import bindings are not supported",
                code="IMPORT_MULTIPLE_BINDINGS_UNSUPPORTED",
            )
        alias = node.names[0]
        binding = alias.asname.name.value if alias.asname else _leftmost_binding_name(alias.name)
        module_name = _module_code(module, node.module)
        imported_name = _module_code(module, alias.name)
        return (
            _ImportSpec(
                kind="from",
                module_name=module_name,
                imported_name=imported_name,
                binding=binding,
                canonical_statement=canonical_statement,
            ),
            statement_line,
        )

    raise GitError("Import statement is invalid", code="IMPORT_STATEMENT_INVALID")


def _existing_import_specs(module: ast.Module) -> list[_ImportSpec]:
    specs: list[_ImportSpec] = []
    for node in module.body:
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.Import):
            for alias in node.names:
                binding = alias.asname or alias.name.split(".", 1)[0]
                specs.append(
                    _ImportSpec(
                        kind="import",
                        module_name=alias.name,
                        imported_name=alias.name,
                        binding=binding,
                        canonical_statement=ast.unparse(node),
                    )
                )
        else:
            module_name = node.module or ""
            if node.level:
                module_name = "." * node.level + module_name
            for alias in node.names:
                binding = alias.asname or alias.name
                specs.append(
                    _ImportSpec(
                        kind="from",
                        module_name=module_name,
                        imported_name=alias.name,
                        binding=binding,
                        canonical_statement=ast.unparse(node),
                    )
                )
    return specs


def _find_import_insertion_index(module: cst.Module) -> int:
    body = list(module.body)
    index = 0
    if body:
        first = body[0]
        if (
            isinstance(first, cst.SimpleStatementLine)
            and len(first.body) == 1
            and isinstance(first.body[0], cst.Expr)
            and isinstance(first.body[0].value, cst.SimpleString)
        ):
            index = 1
    while index < len(body):
        stmt = body[index]
        if not isinstance(stmt, cst.SimpleStatementLine) or len(stmt.body) != 1:
            break
        node = stmt.body[0]
        if isinstance(node, cst.Import):
            index += 1
            continue
        if isinstance(node, cst.ImportFrom):
            relative = getattr(node, "relative", None)
            if relative:
                break
            if node.module is None:
                break
            index += 1
            continue
        break
    return index


def _clone_statement_line(statement_line: cst.SimpleStatementLine) -> cst.SimpleStatementLine:
    return statement_line.deep_clone()


def _apply_import_statement(
    module_text: str,
    statement: str,
) -> tuple[str, _ImportSpec, cst.SimpleStatementLine]:
    module = cst.parse_module(module_text)
    requested_spec, statement_line = _parse_import_statement(statement)
    module_ast = ast.parse(module_text)
    existing_specs = _existing_import_specs(module_ast)

    for existing in existing_specs:
        if (
            existing.kind == requested_spec.kind
            and existing.module_name == requested_spec.module_name
            and existing.imported_name == requested_spec.imported_name
            and existing.binding == requested_spec.binding
        ):
            raise GitError("The requested import already exists.", code="IMPORT_ALREADY_EXISTS")
        if existing.binding == requested_spec.binding and (
            existing.kind != requested_spec.kind
            or existing.module_name != requested_spec.module_name
            or existing.imported_name != requested_spec.imported_name
        ):
            raise GitError("The requested import binding already exists.", code="IMPORT_BINDING_CONFLICT")

    insertion_index = _find_import_insertion_index(module)
    updated_body = list(module.body)
    updated_body.insert(insertion_index, _clone_statement_line(statement_line))
    updated_module = module.with_changes(body=tuple(updated_body))
    return updated_module.code, requested_spec, statement_line


def _decorator_terminal_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        return _decorator_terminal_name(node.func)
    return None


def _decorator_structure_key(expression: ast.AST) -> str:
    return ast.dump(expression, include_attributes=False)


def _decorator_is_conflicting_family(expression: ast.AST) -> bool:
    return _decorator_terminal_name(expression) in {"staticmethod", "classmethod", "property"}


def _decorator_can_target(node: ast.AST) -> bool:
    return isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))


class _DecoratorInserter(cst.CSTTransformer):
    def __init__(self, target_qname: str, decorator_expression: cst.BaseExpression, position: str) -> None:
        self.target_qname = target_qname
        self.decorator_expression = decorator_expression
        self.position = position
        self.scope: list[str] = []
        self.function_stack: list[bool] = []
        self.class_stack: list[bool] = []
        self.matched = False

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        self.scope.append(node.name.value)
        self.class_stack.append(".".join(self.scope) == self.target_qname)

    def leave_ClassDef(self, original_node: cst.ClassDef, updated_node: cst.ClassDef) -> cst.CSTNode:
        is_target = self.class_stack.pop()
        self.scope.pop()
        if not is_target:
            return updated_node
        if self.position == "outermost":
            decorators = (cst.Decorator(decorator=self.decorator_expression), *updated_node.decorators)
        else:
            decorators = (*updated_node.decorators, cst.Decorator(decorator=self.decorator_expression))
        self.matched = True
        return updated_node.with_changes(decorators=decorators)

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        self.scope.append(node.name.value)
        self.function_stack.append(".".join(self.scope) == self.target_qname)

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.CSTNode:
        is_target = self.function_stack.pop()
        self.scope.pop()
        if not is_target:
            return updated_node
        if self.position == "outermost":
            decorators = (cst.Decorator(decorator=self.decorator_expression), *updated_node.decorators)
        else:
            decorators = (*updated_node.decorators, cst.Decorator(decorator=self.decorator_expression))
        self.matched = True
        return updated_node.with_changes(decorators=decorators)


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

        def leave_ClassDef(self, original_node: cst.ClassDef, updated_node: cst.ClassDef) -> cst.CSTNode:
            is_target = self.class_stack.pop()
            self.scope.pop()
            if not is_target:
                return updated_node
            decorators = list(updated_node.decorators)
            index = 0 if target_position == "outermost" else len(decorators) - 1
            if index < 0:
                return updated_node
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
            if index < 0:
                return updated_node
            if 0 <= index < len(decorators):
                decorator = decorators[index]
                if module.code_for_node(decorator.decorator).strip() == target_decorator:
                    del decorators[index]
                    self.matched = True
            return updated_node.with_changes(decorators=tuple(decorators))

    remover = _DecoratorRemover()
    updated_module = module.visit(remover)
    return updated_module, remover.matched


def add_decorator(
    file_path: Path,
    target: str,
    decorator: str,
    position: str,
    *,
    project_root: Path | None = None,
    db_path: Path | None = None,
    run_tests: bool = False,
    test_command: str | None = None,
    dry_run: bool = False,
) -> AddDecoratorResult:
    file_path = file_path.resolve()
    if not file_path.exists():
        raise GitError("File does not exist", code="FILE_NOT_FOUND")
    if not decorator.strip():
        raise GitError("Decorator expression is required", code="DECORATOR_REQUIRED")
    if not position.strip():
        raise GitError("Decorator position is required", code="DECORATOR_POSITION_REQUIRED")
    if position not in {"outermost", "innermost"}:
        raise GitError("Decorator position is invalid", code="DECORATOR_POSITION_INVALID")

    decorator_expression = _validate_decorator_expression(decorator)
    decorator_ast = ast.parse(decorator, mode="eval").body
    canonical_decorator = ast.unparse(decorator_ast)

    context = ensure_clean_git_repo(project_root or file_path.parent)
    if not is_within_root(file_path, context.root):
        raise GitError("File is outside the authorized project root", code="FILE_OUTSIDE_PROJECT")

    records = scan_file(file_path)
    target_record = _resolve_decorator_target(records, target)
    target_qname = target_record.qualified_name
    target_kind = target_record.type

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
            operation="add-decorator",
            symbol=target_qname,
            decorator_expression=canonical_decorator,
            decorator_position=position,
            decorator_target_kind=target_kind,
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
            operation="add-decorator",
            symbol=target_qname,
            decorator_expression=canonical_decorator,
            decorator_position=position,
            decorator_target_kind=target_kind,
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

    if not _decorator_can_target(node):
        raise GitError("Target is not a supported decorator target", code="DECORATOR_TARGET_UNSUPPORTED")

    requested_key = _decorator_structure_key(decorator_ast)
    requested_family = _decorator_terminal_name(decorator_ast)
    existing_family_conflicts = []
    for existing in getattr(node, "decorator_list", []):
        existing_key = _decorator_structure_key(existing)
        if existing_key == requested_key:
            _write_state(
                project_root=context.root,
                file_path=file_path,
                db_path=db_path,
                operation="add-decorator",
                symbol=target_qname,
                decorator_expression=canonical_decorator,
                decorator_position=position,
                decorator_target_kind=target_kind,
                before_sha256=before_sha256,
                after_sha256=None,
                git_diff_text=None,
                pytest_command=None,
                pytest_exit_code=None,
                pytest_status=None,
                status="refused",
                message="Target already has the requested decorator",
            )
            raise GitError("The requested decorator already exists on the target.", code="DECORATOR_ALREADY_EXISTS")
        if (
            target_kind in {"function", "method"}
            and _decorator_is_conflicting_family(existing)
            and _decorator_is_conflicting_family(decorator_ast)
            and _decorator_terminal_name(existing) != requested_family
        ):
            existing_family_conflicts.append(existing)

    if existing_family_conflicts:
        raise GitError(
            "The requested decorator conflicts with an existing method binding decorator.",
            code="DECORATOR_CONFLICT",
            details={"symbol": target_qname, "decorator": canonical_decorator},
        )

    cst_module = cst.parse_module(source)
    transformer = _DecoratorInserter(target_qname, decorator_expression, position)
    updated_module = cst_module.visit(transformer)
    if not transformer.matched:
        _write_state(
            project_root=context.root,
            file_path=file_path,
            db_path=db_path,
            operation="add-decorator",
            symbol=target_qname,
            decorator_expression=canonical_decorator,
            decorator_position=position,
            decorator_target_kind=target_kind,
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
        f"Planned decorator insertion: {decorator} ({position})."
        if dry_run
        else f"Added decorator: {decorator} ({position})."
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
            operation="add-decorator",
            symbol=target_qname,
            decorator_expression=canonical_decorator,
            decorator_position=position,
            decorator_target_kind=target_kind,
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
            operation="add-decorator",
            symbol=target_qname,
            decorator_expression=canonical_decorator,
            decorator_position=position,
            decorator_target_kind=target_kind,
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
    return AddDecoratorResult(
        file_path=file_path,
        project_root=context.root,
        db_path=db_path,
        symbol=target_qname,
        target_kind=target_kind,
        decorator=canonical_decorator,
        position=position,
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
    import_statement: str | None = None,
    import_binding: str | None = None,
    decorator_expression: str | None = None,
    decorator_position: str | None = None,
    decorator_target_kind: str | None = None,
    before_sha256: str | None,
    after_sha256: str | None,
    git_diff_text: str | None,
    pytest_command: str | None,
    pytest_exit_code: int | None,
    pytest_status: str | None,
    status: str,
    message: str | None,
    expected_return_annotation: str | None = None,
    return_annotation: str | None = None,
) -> int | None:
    record = OperationRecord(
        created_at=now_utc_iso(),
        project_path=str(project_root),
        file_path=str(file_path),
        operation=operation,
        symbol=symbol,
        parameter=parameter,
        import_statement=import_statement,
        import_binding=import_binding,
        decorator_expression=decorator_expression,
        decorator_position=decorator_position,
        decorator_target_kind=decorator_target_kind,
        before_sha256=before_sha256,
        after_sha256=after_sha256,
        git_diff=git_diff_text,
        pytest_command=pytest_command,
        pytest_exit_code=pytest_exit_code,
        pytest_status=pytest_status,
        status=status,
        message=message,
        expected_return_annotation=expected_return_annotation,
        return_annotation=return_annotation,
    )
    operation_id: int | None = None
    if db_path is not None and status not in {"planned", "refused"}:
        operation_id = insert_record(db_path, record)
    write_last_operation(replace(record, operation_id=operation_id))
    return operation_id


def add_import(
    file_path: Path,
    statement: str,
    *,
    project_root: Path | None = None,
    db_path: Path | None = None,
    run_tests: bool = False,
    test_command: str | None = None,
    dry_run: bool = False,
) -> AddImportResult:
    file_path = file_path.resolve()
    if not file_path.exists():
        raise GitError("File does not exist", code="FILE_NOT_FOUND")

    context = ensure_clean_git_repo(project_root or file_path.parent)
    if not is_within_root(file_path, context.root):
        raise GitError("File is outside the authorized project root", code="FILE_OUTSIDE_PROJECT")

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
            operation="add-import",
            symbol=None,
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

    updated_source, requested_spec, _statement_line = _apply_import_statement(source, statement)
    preview_diff_text = _preview_diff(file_path, source, updated_source)

    if dry_run:
        after_sha256 = before_sha256
    else:
        updated_bytes = _encode_python_text(updated_source, bom, encoding)
        file_path.write_bytes(updated_bytes)
        after_sha256 = sha256_file(file_path)

    stat, diff_text = git_diff(context.root) if not dry_run else ("", "")

    pytest_exit_code: int | None = None
    pytest_status: str | None = None
    pytest_command = None
    status = "planned" if dry_run else "applied"
    message = (
        f"Planned import statement: {requested_spec.canonical_statement}."
        if dry_run
        else f"Added import statement: {requested_spec.canonical_statement}."
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
            operation="add-import",
            symbol=requested_spec.binding,
            import_statement=requested_spec.canonical_statement,
            import_binding=requested_spec.binding,
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
            operation="add-import",
            symbol=requested_spec.binding,
            import_statement=requested_spec.canonical_statement,
            import_binding=requested_spec.binding,
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
    return AddImportResult(
        file_path=file_path,
        project_root=context.root,
        db_path=db_path,
        symbol=requested_spec.binding,
        binding=requested_spec.binding,
        statement=requested_spec.canonical_statement,
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


class _ReturnTypeRemover(cst.CSTTransformer):
    def __init__(self, target_qname: str, expected_annotation: str, module: cst.Module) -> None:
        self.target_qname = target_qname
        self.expected_annotation = expected_annotation
        self.module = module
        self.expected_annotation_expression = _validate_expected_return_annotation(expected_annotation)
        self.scope: list[str] = []
        self.function_stack: list[bool] = []
        self.matched = False
        self.removed_annotation_source: str | None = None

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
        if not is_target:
            return
        if node.returns is None:
            raise GitError(
                "Target does not contain a return annotation",
                code="RETURN_ANNOTATION_NOT_FOUND",
                details={"symbol": self.target_qname},
            )
        if not self.expected_annotation_expression.deep_equals(node.returns.annotation):
            actual_annotation = self.module.code_for_node(node.returns.annotation).strip()
            raise GitError(
                "Target return annotation does not match the expected annotation",
                code="RETURN_ANNOTATION_MISMATCH",
                details={
                    "symbol": self.target_qname,
                    "expected_annotation": self.expected_annotation,
                    "actual_annotation": actual_annotation,
                },
            )
        self.removed_annotation_source = self.module.code_for_node(node.returns.annotation).strip()

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.CSTNode:
        is_target = self.function_stack.pop()
        if not is_target:
            return updated_node
        if updated_node.returns is None:
            raise GitError(
                "Target does not contain a return annotation",
                code="RETURN_ANNOTATION_NOT_FOUND",
                details={"symbol": self.target_qname},
            )
        self.matched = True
        return updated_node.with_changes(returns=None)


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


def remove_return_type(
    file_path: Path,
    target: str,
    expected_annotation: str,
    *,
    project_root: Path | None = None,
    db_path: Path | None = None,
    run_tests: bool = False,
    test_command: str | None = None,
    dry_run: bool = False,
) -> RemoveReturnTypeResult:
    file_path = file_path.resolve()
    if not file_path.exists():
        raise GitError("File does not exist", code="FILE_NOT_FOUND")

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
            operation="remove-return-type",
            symbol=target_qname,
            expected_return_annotation=expected_annotation,
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
            operation="remove-return-type",
            symbol=target_qname,
            expected_return_annotation=expected_annotation,
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
    if node.returns is None:
        _write_state(
            project_root=context.root,
            file_path=file_path,
            db_path=db_path,
            operation="remove-return-type",
            symbol=target_qname,
            expected_return_annotation=expected_annotation,
            before_sha256=before_sha256,
            after_sha256=None,
            git_diff_text=None,
            pytest_command=None,
            pytest_exit_code=None,
            pytest_status=None,
            status="refused",
            message="Target does not contain a return annotation",
        )
        raise GitError(
            "Target does not contain a return annotation",
            code="RETURN_ANNOTATION_NOT_FOUND",
            details={"symbol": target_qname},
        )

    cst_module = cst.parse_module(source)
    transformer = _ReturnTypeRemover(target_qname, expected_annotation, cst_module)
    updated_module = cst_module.visit(transformer)
    if not transformer.matched:
        _write_state(
            project_root=context.root,
            file_path=file_path,
            db_path=db_path,
            operation="remove-return-type",
            symbol=target_qname,
            expected_return_annotation=expected_annotation,
            before_sha256=before_sha256,
            after_sha256=None,
            git_diff_text=None,
            pytest_command=None,
            pytest_exit_code=None,
            pytest_status=None,
            status="refused",
            message="Target return annotation did not match the expected annotation",
        )
        raise GitError(
            "Target return annotation does not match the expected annotation",
            code="RETURN_ANNOTATION_MISMATCH",
            details={"symbol": target_qname, "expected_annotation": expected_annotation},
        )

    removed_annotation_source = transformer.removed_annotation_source or ""
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
        f"Planned return annotation removal: {removed_annotation_source}."
        if dry_run
        else f"Removed return annotation: {removed_annotation_source}."
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
            operation="remove-return-type",
            symbol=target_qname,
            expected_return_annotation=expected_annotation,
            return_annotation=removed_annotation_source,
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
            operation="remove-return-type",
            symbol=target_qname,
            expected_return_annotation=expected_annotation,
            return_annotation=removed_annotation_source,
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
    return RemoveReturnTypeResult(
        file_path=file_path,
        project_root=context.root,
        db_path=db_path,
        symbol=target_qname,
        expected_annotation=expected_annotation,
        annotation=removed_annotation_source,
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
