from __future__ import annotations

import ast
import difflib
import subprocess
from dataclasses import dataclass
from pathlib import Path

import libcst as cst

from .datasette_log import OperationRecord, now_utc_iso, write_last_operation
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
        matches = [record for record in records if record.qualified_name == target]
    else:
        matches = [
            record
            for record in records
            if record.qualified_name.split(".")[-1] == target
            and record.type in {"function", "method"}
        ]
    if not matches:
        raise GitError("Target symbol not found")
    if len(matches) > 1:
        raise GitError("Target symbol is ambiguous")
    return matches[0].qualified_name


def _run_pytest(command: str, cwd: Path) -> tuple[int, str]:
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
    operation: str,
    symbol: str | None,
    before_sha256: str | None,
    after_sha256: str | None,
    git_diff_text: str | None,
    pytest_command: str | None,
    pytest_exit_code: int | None,
    pytest_status: str | None,
    status: str,
    message: str | None,
) -> None:
    write_last_operation(
        OperationRecord(
            created_at=now_utc_iso(),
            project_path=str(project_root),
            file_path=str(file_path),
            operation=operation,
            symbol=symbol,
            before_sha256=before_sha256,
            after_sha256=after_sha256,
            git_diff=git_diff_text,
            pytest_command=pytest_command,
            pytest_exit_code=pytest_exit_code,
            pytest_status=pytest_status,
            status=status,
            message=message,
        )
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
                    raise GitError("Target already has a docstring")

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


def add_docstring(
    file_path: Path,
    target: str,
    *,
    project_root: Path | None = None,
    run_tests: bool = False,
    test_command: str | None = None,
    dry_run: bool = False,
) -> AddDocstringResult:
    file_path = file_path.resolve()
    if not file_path.exists():
        raise GitError("File does not exist")

    context = ensure_clean_git_repo(project_root or file_path.parent)
    if not is_within_root(file_path, context.root):
        raise GitError("File is outside the authorized project root")

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
        raise GitError(f"LibCST parse failed: {exc}") from exc

    module = ast.parse(source, filename=str(file_path))
    node = _find_target_node(module, target_qname)
    if node is None:
        _write_state(
            project_root=context.root,
            file_path=file_path,
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
        raise GitError("Target symbol not found")

    if _has_docstring(node):
        _write_state(
            project_root=context.root,
            file_path=file_path,
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
        raise GitError("Target already has a docstring")

    cst_module = cst.parse_module(source)
    transformer = _DocstringInserter(target_qname)
    updated_module = cst_module.visit(transformer)
    if not transformer.matched:
        _write_state(
            project_root=context.root,
            file_path=file_path,
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
        raise GitError("Target symbol not found")

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

    if run_tests:
        pytest_command = test_command or "pytest"
        pytest_exit_code, pytest_output = _run_pytest(pytest_command, cwd=context.root)
        pytest_status = "passed" if pytest_exit_code == 0 else "failed"
        if pytest_output:
            message = f"{message} Pytest output: {pytest_output}"
        if not dry_run:
            status = "tested" if pytest_exit_code == 0 else "failed"
        else:
            status = "planned"

    if not dry_run:
        _write_state(
            project_root=context.root,
            file_path=file_path,
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

    return AddDocstringResult(
        file_path=file_path,
        project_root=context.root,
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
    )
