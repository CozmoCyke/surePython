from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path


class GitError(RuntimeError):
    pass


@dataclass(frozen=True)
class GitContext:
    root: Path


def run_git(args: list[str], cwd: Path) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise GitError((completed.stderr or completed.stdout).strip() or "git failed")
    return completed.stdout


def find_git_root(path: Path) -> Path | None:
    try:
        output = run_git(["rev-parse", "--show-toplevel"], cwd=path)
    except GitError:
        return None
    return Path(output.strip())


def is_clean_repo(root: Path) -> bool:
    output = run_git(["status", "--porcelain"], cwd=root)
    return output.strip() == ""


def ensure_git_context(path: Path) -> GitContext:
    root = find_git_root(path)
    if root is None:
        raise GitError("Not a git repository")
    return GitContext(root=root)


def ensure_clean_git_repo(path: Path) -> GitContext:
    context = ensure_git_context(path)
    if not is_clean_repo(context.root):
        raise GitError("Git status is not clean")
    return context


def is_within_root(path: Path, root: Path) -> bool:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError:
        return False
    return True


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_diff(root: Path) -> tuple[str, str]:
    stat = run_git(["diff", "--stat"], cwd=root)
    diff = run_git(["diff"], cwd=root)
    return stat, diff

