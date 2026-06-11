from __future__ import annotations

import ast
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
    git_stat: str
    git_diff_text: str
    pytest_command: str | None
    pytest_exit_code: int | None
    pytest_status: str | None
    status: str
    message: str


def _classify_node(node: ast.AST, class_stack: list[str]) -> str:
    return "method" if class_stack else "function"


def _has_docstring(node: ast.AST) -> bool:
    return ast.get_docstring(node) is not None


def _load_lines(source: str) -> list[str]:
    lines = source.splitlines(keepends=True)
    if not lines:
        return [""]
    return lines


def _insert_docstring(source: str, node: ast.AST) -> str:
    lines = _load_lines(source)
    body = getattr(node, "body", None)
    if not isinstance(body, list) or not body:
        raise GitError("Target body is empty")
    first_stmt = body[0]
    first_line_index = getattr(first_stmt, "lineno", None)
    if first_line_index is None:
        raise GitError("Unable to locate function body")
    line_text = lines[first_line_index - 1]
    indent = line_text[: len(line_text) - len(line_text.lstrip())]
    lines.insert(first_line_index - 1, f"{indent}{TODO_DOCSTRING}\n")
    return "".join(lines)


def _find_target_node(module: ast.Module, target_qname: str) -> ast.AST:
    parts = target_qname.split(".")

    def walk(nodes: list[ast.AST], prefix: list[str], class_stack: list[str]) -> ast.AST | None:
        for node in nodes:
            if isinstance(node, ast.ClassDef):
                qname = ".".join([*prefix, node.name])
                if qname == target_qname:
                    return node
                found = walk(node.body, [*prefix, node.name], [*class_stack, node.name])
                if found is not None:
                    return found
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qname = ".".join([*prefix, node.name])
                if qname == target_qname:
                    return node
        return None

    return walk(module.body, [], [])  # type: ignore[return-value]


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


def add_docstring(
    file_path: Path,
    target: str,
    *,
    project_root: Path | None = None,
    run_tests: bool = False,
    test_command: str | None = None,
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

    updated_source = _insert_docstring(source, node)
    file_path.write_text(updated_source, encoding="utf-8")
    after_sha256 = sha256_file(file_path)

    stat, diff_text = git_diff(context.root)

    pytest_exit_code: int | None = None
    pytest_status: str | None = None
    pytest_command = None
    status = "applied"
    message = "Added skeleton docstring."

    if run_tests:
        pytest_command = test_command or "pytest"
        pytest_exit_code, pytest_output = _run_pytest(pytest_command, cwd=context.root)
        pytest_status = "passed" if pytest_exit_code == 0 else "failed"
        if pytest_output:
            message = f"{message} Pytest output: {pytest_output}"
        status = "tested" if pytest_exit_code == 0 else "failed"

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
        git_stat=stat,
        git_diff_text=diff_text,
        pytest_command=pytest_command,
        pytest_exit_code=pytest_exit_code,
        pytest_status=pytest_status,
        status=status,
        message=message,
    )

