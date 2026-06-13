from __future__ import annotations

import json
import subprocess
import sys

from surepython.cli import main


def test_capabilities_json_lists_supported_operations(capsys) -> None:
    exit_code = main(["capabilities", "--format", "json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    operations = {operation["name"]: operation for operation in payload["operations"]}
    assert set(operations) == {"add-docstring", "add-return-type"}
    assert operations["add-docstring"]["supports_rollback"] is True
    assert operations["add-return-type"]["targets"] == ["function", "method"]
    assert operations["add-return-type"]["required_arguments"] == [
        "file",
        "function",
        "annotation",
    ]


def test_capabilities_text_is_human_readable(capsys) -> None:
    exit_code = main(["capabilities"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "add-docstring" in output
    assert "add-return-type" in output


def test_python_m_surepython_propagates_exit_code() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "surepython", "capabilities", "--format", "xml"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "invalid choice" in completed.stderr.lower()
