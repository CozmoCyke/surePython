from __future__ import annotations

import subprocess
import sqlite3
from pathlib import Path

import pytest

from surepython.cli import main
from surepython.codemods import add_docstring
from surepython.git_tools import GitError
from surepython.rollback import rollback_last


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_module.py"


def init_git_repo(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "surepython@example.com"], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "SurePython"], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "baseline"], cwd=str(root), check=True, capture_output=True, text=True)


def commit_all(root: Path, message: str) -> None:
    subprocess.run(["git", "add", "."], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", message], cwd=str(root), check=True, capture_output=True, text=True)


def write_fixture_file(root: Path) -> Path:
    sample = root / "sample.py"
    sample.write_text(FIXTURE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    return sample


def git_status_short(root: Path) -> str:
    completed = subprocess.run(
        ["git", "status", "--short"],
        cwd=str(root),
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def read_operations(db_path: Path) -> list[tuple[str, str, str | None]]:
    with sqlite3.connect(str(db_path)) as connection:
        return connection.execute(
            """
            SELECT operation, status, symbol
            FROM surepython_operations
            ORDER BY id
            """
        ).fetchall()


def prepare_logged_add_docstring(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "project"
    root.mkdir()
    sample = write_fixture_file(root)
    init_git_repo(root)
    db_path = tmp_path / "surepython_lab.db"

    add_docstring(sample, "SampleClass.sample_method", project_root=root, db_path=db_path)
    commit_all(root, "apply docstring")

    return root, sample, db_path


def test_rollback_last_dry_run_shows_diff_without_writing(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root, sample, db_path = prepare_logged_add_docstring(tmp_path)
    before = sample.read_text(encoding="utf-8")

    exit_code = main(["rollback", "--last", "--db", str(db_path), "--dry-run"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Dry run; no files changed." in output
    assert "Rollback diff:" in output
    assert '-        """TODO: Document this function."""' in output
    assert sample.read_text(encoding="utf-8") == before
    assert git_status_short(root) == ""


def test_rollback_last_applies_single_logged_add_docstring(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root, sample, db_path = prepare_logged_add_docstring(tmp_path)

    result = rollback_last(db_path)
    updated = sample.read_text(encoding="utf-8")

    assert result.status == "rolled_back"
    assert '"""TODO: Document this function."""' not in updated
    assert git_status_short(root) != ""
    assert read_operations(db_path) == [
        ("add-docstring", "applied", "SampleClass.sample_method"),
        ("rollback", "rolled_back", "SampleClass.sample_method"),
    ]


def test_rollback_cli_requires_db(capsys) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["rollback", "--last", "--dry-run"])

    assert excinfo.value.code == 2
    assert "--db" in capsys.readouterr().err


def test_rollback_refuses_dirty_git_status(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root, sample, db_path = prepare_logged_add_docstring(tmp_path)
    sample.write_text(sample.read_text(encoding="utf-8") + "\n# dirty\n", encoding="utf-8")

    try:
        rollback_last(db_path, dry_run=True)
    except GitError as exc:
        assert "git status" in str(exc).lower()
    else:
        raise AssertionError("Expected dirty repo refusal")

    assert git_status_short(root) != ""


def test_rollback_refuses_hash_mismatch(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root, sample, db_path = prepare_logged_add_docstring(tmp_path)
    sample.write_text(sample.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
    commit_all(root, "change after logged operation")

    try:
        rollback_last(db_path, dry_run=True)
    except GitError as exc:
        assert "after_sha256" in str(exc)
    else:
        raise AssertionError("Expected hash mismatch refusal")
