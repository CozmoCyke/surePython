from pathlib import Path
import subprocess

from surepython.codemods import add_docstring
from surepython.datasette_log import read_last_operation


def init_git_repo(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "surepython@example.com"], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "SurePython"], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=str(root), check=True, capture_output=True, text=True)


def test_add_docstring_inserts_skeleton(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = root / "sample.py"
    sample.write_text("def run_audit():\n    return 1\n", encoding="utf-8")
    init_git_repo(root)

    result = add_docstring(sample, "run_audit", project_root=root)

    assert '"""TODO: Document this function."""' in sample.read_text(encoding="utf-8")
    assert result.symbol == "run_audit"
    assert result.status == "applied"
    assert "1 file changed" in result.git_stat or result.git_stat.strip() != ""

    record = read_last_operation()
    assert record.operation == "add-docstring"
    assert record.symbol == "run_audit"


def test_add_docstring_refuses_existing_docstring(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = root / "sample.py"
    sample.write_text(
        'def run_audit():\n    """Existing."""\n    return 1\n',
        encoding="utf-8",
    )
    init_git_repo(root)

    try:
        add_docstring(sample, "run_audit", project_root=root)
    except Exception as exc:
        assert "docstring" in str(exc).lower()
    else:
        raise AssertionError("Expected refusal")

