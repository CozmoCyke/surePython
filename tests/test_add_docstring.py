from __future__ import annotations

import subprocess
from pathlib import Path

from surepython.codemods import add_docstring
from surepython.datasette_log import read_last_operation
from surepython.git_tools import GitError


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_module.py"


def init_git_repo(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "surepython@example.com"], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "SurePython"], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=str(root), check=True, capture_output=True, text=True)


def write_fixture_file(root: Path, content: str | None = None) -> Path:
    sample = root / "sample.py"
    sample.write_text(content or FIXTURE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    return sample


def test_add_docstring_inserts_skeleton_for_global_function(tmp_path: Path, monkeypatch) -> None:
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


def test_add_docstring_inserts_skeleton_for_class_method(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_fixture_file(root)
    init_git_repo(root)

    result = add_docstring(sample, "SampleClass.sample_method", project_root=root)
    updated = sample.read_text(encoding="utf-8")

    assert result.symbol == "SampleClass.sample_method"
    assert result.status == "applied"
    assert updated.count('"""TODO: Document this function."""') == 1
    assert 'def sample_method():\n    return "global"\n' in updated
    assert (
        'class SampleClass:\n    def sample_method(self):\n        """TODO: Document this function."""\n        return "class"\n'
        in updated
    )
    assert 'class OtherClass:\n    def sample_method(self):\n        return "other"\n' in updated


def test_add_docstring_refuses_existing_docstring_in_class_method(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_fixture_file(
        root,
        FIXTURE_PATH.read_text(encoding="utf-8").replace(
            '    def sample_method(self):\n        return "class"\n',
            '    def sample_method(self):\n        """Existing."""\n        return "class"\n',
        ),
    )
    init_git_repo(root)

    try:
        add_docstring(sample, "SampleClass.sample_method", project_root=root)
    except GitError as exc:
        assert "docstring" in str(exc).lower()
    else:
        raise AssertionError("Expected refusal")


def test_add_docstring_refuses_unknown_class(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_fixture_file(root)
    init_git_repo(root)

    try:
        add_docstring(sample, "MissingClass.sample_method", project_root=root)
    except GitError as exc:
        assert "not found" in str(exc).lower()
    else:
        raise AssertionError("Expected refusal")


def test_add_docstring_refuses_unknown_method(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_fixture_file(root)
    init_git_repo(root)

    try:
        add_docstring(sample, "SampleClass.missing_method", project_root=root)
    except GitError as exc:
        assert "not found" in str(exc).lower()
    else:
        raise AssertionError("Expected refusal")


def test_add_docstring_refuses_ambiguous_unqualified_method_name(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root = tmp_path / "project"
    root.mkdir()
    sample = write_fixture_file(root)
    init_git_repo(root)

    try:
        add_docstring(sample, "sample_method", project_root=root)
    except GitError as exc:
        assert "ambiguous" in str(exc).lower()
    else:
        raise AssertionError("Expected refusal")

