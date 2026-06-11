from pathlib import Path

from surepython.scanner import scan_file, scan_project


def test_scan_file_reports_functions_classes_and_methods(tmp_path: Path) -> None:
    sample = tmp_path / "module.py"
    sample.write_text(
        """
class Example:
    def method(self):
        \"\"\"Doc.\"\"\"
        return 1


def top_level():
    return 2
""".strip()
        + "\n",
        encoding="utf-8",
    )

    records = scan_file(sample)
    assert [record.type for record in records] == ["class", "method", "function"]
    assert records[0].qualified_name == "Example"
    assert records[1].qualified_name == "Example.method"
    assert records[1].has_docstring is True
    assert records[2].qualified_name == "top_level"


def test_scan_project_walks_python_files(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    (root / "b.py").write_text("class B:\n    def c(self):\n        return 2\n", encoding="utf-8")

    records = scan_project(root)
    assert {record.qualified_name for record in records} == {"a", "B", "B.c"}

