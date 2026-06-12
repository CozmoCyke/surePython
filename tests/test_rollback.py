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


def write_bytes_fixture_file(root: Path, content: bytes) -> Path:
    sample = root / "sample.py"
    sample.write_bytes(content)
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


def prepare_logged_add_docstring_bytes(
    tmp_path: Path, content: bytes
) -> tuple[Path, Path, Path, bytes]:
    root = tmp_path / "project"
    root.mkdir()
    sample = write_bytes_fixture_file(root, content)
    original = sample.read_bytes()
    init_git_repo(root)
    db_path = tmp_path / "surepython_lab.db"

    add_docstring(sample, "SampleClass.sample_method", project_root=root, db_path=db_path)
    commit_all(root, "apply docstring")

    return root, sample, db_path, original


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


def test_rollback_restores_lf_bytes_exactly(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    content = (
        b"class SampleClass:\n"
        b"    def sample_method(self):\n"
        b"        return 'class'\n"
    )
    _, sample, db_path, original = prepare_logged_add_docstring_bytes(tmp_path, content)

    result = rollback_last(db_path)

    assert result.status == "rolled_back"
    assert sample.read_bytes() == original


def test_rollback_restores_crlf_bytes_exactly(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    content = (
        b"class SampleClass:\r\n"
        b"    def sample_method(self):\r\n"
        b"        return 'class'\r\n"
    )
    _, sample, db_path, original = prepare_logged_add_docstring_bytes(tmp_path, content)

    result = rollback_last(db_path)

    assert result.status == "rolled_back"
    assert sample.read_bytes() == original


def test_rollback_preserves_final_newline(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    content = (
        b"class SampleClass:\n"
        b"    def sample_method(self):\n"
        b"        return 'class'\n"
    )
    _, sample, db_path, original = prepare_logged_add_docstring_bytes(tmp_path, content)

    rollback_last(db_path)

    assert sample.read_bytes().endswith(b"\n")
    assert sample.read_bytes() == original


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


def test_rollback_refuses_when_restored_bytes_do_not_match_before_sha(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root, sample, db_path = prepare_logged_add_docstring(tmp_path)
    before_refusal = sample.read_bytes()
    with sqlite3.connect(str(db_path)) as connection:
        connection.execute(
            "UPDATE surepython_operations SET before_sha256 = ? WHERE operation = ?",
            ("0" * 64, "add-docstring"),
        )
        connection.commit()

    try:
        rollback_last(db_path)
    except GitError as exc:
        assert "before_sha256" in str(exc)
    else:
        raise AssertionError("Expected restored hash refusal")

    assert sample.read_bytes() == before_refusal
    assert git_status_short(root) == ""


def test_windows_smoke_add_docstring_commit_then_real_rollback(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    content = (
        b"class SampleClass:\r\n"
        b"    def sample_method(self):\r\n"
        b"        return 'class'\r\n"
    )
    root, sample, db_path, original = prepare_logged_add_docstring_bytes(tmp_path, content)

    rollback_last(db_path)

    assert sample.read_bytes() == original
    assert git_status_short(root) != ""
