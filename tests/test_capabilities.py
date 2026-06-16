from __future__ import annotations

import json
import subprocess
import sys

from surepython.capabilities import serialize_capabilities
from surepython.cli import main


def test_capabilities_json_lists_supported_operations(capsys) -> None:
    exit_code = main(["capabilities", "--format", "json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert list(payload) == [
        "protocol_schema_version",
        "capabilities_schema_version",
        "operations",
        "commands",
    ]
    assert payload["protocol_schema_version"] == "1.0"
    assert payload["capabilities_schema_version"] == "1.0"
    operations = {operation["name"]: operation for operation in payload["operations"]}
    assert set(operations) == {
        "add-docstring",
        "remove-docstring",
        "add-return-type",
        "remove-return-type",
        "add-parameter-type",
        "remove-parameter-type",
        "add-import",
        "add-decorator",
        "remove-decorator",
        "remove-import",
    }
    assert operations["add-docstring"]["supports_rollback"] is True
    assert operations["remove-docstring"]["targets"] == ["module", "class", "function", "method"]
    assert operations["remove-docstring"]["required_arguments"] == [
        "file",
        "symbol",
        "expect-docstring",
    ]
    assert "DOCSTRING_REQUIRED" in operations["remove-docstring"]["possible_error_codes"]
    assert "DOCSTRING_NOT_FOUND" in operations["remove-docstring"]["possible_error_codes"]
    assert "DOCSTRING_MISMATCH" in operations["remove-docstring"]["possible_error_codes"]
    assert "DOCSTRING_INLINE_SUITE_UNSUPPORTED" in operations["remove-docstring"]["possible_error_codes"]
    assert "DOCSTRING_REPRESENTATION_UNSUPPORTED" not in operations["remove-docstring"]["possible_error_codes"]
    assert operations["add-return-type"]["targets"] == ["function", "method"]
    assert operations["add-return-type"]["required_arguments"] == [
        "file",
        "function",
        "annotation",
    ]
    assert "json" in operations["add-docstring"]["supported_formats"]
    assert "ANNOTATION_INVALID" in operations["add-return-type"]["possible_error_codes"]
    assert operations["remove-return-type"]["targets"] == ["function", "method"]
    assert operations["remove-return-type"]["required_arguments"] == [
        "file",
        "function",
        "expect-annotation",
    ]
    assert "RETURN_ANNOTATION_MISMATCH" in operations["remove-return-type"]["possible_error_codes"]
    assert operations["remove-parameter-type"]["targets"] == ["function", "method"]
    assert operations["remove-parameter-type"]["required_arguments"] == [
        "file",
        "function",
        "parameter",
        "expect-annotation",
    ]
    assert operations["remove-parameter-type"]["supported_parameter_kinds"] == [
        "positional-only",
        "positional-or-keyword",
        "keyword-only",
    ]
    assert operations["remove-parameter-type"]["unsupported_parameter_kinds"] == [
        "var-positional",
        "var-keyword",
    ]
    assert "PARAMETER_ANNOTATION_MISMATCH" in operations["remove-parameter-type"]["possible_error_codes"]
    assert "PARAMETER_AMBIGUOUS" not in operations["remove-parameter-type"]["possible_error_codes"]
    assert operations["add-parameter-type"]["supported_parameter_kinds"] == [
        "positional-only",
        "positional-or-keyword",
        "keyword-only",
    ]
    assert operations["add-parameter-type"]["unsupported_parameter_kinds"] == [
        "var-positional",
        "var-keyword",
    ]
    assert "PARAMETER_KIND_UNSUPPORTED" in operations["add-parameter-type"]["possible_error_codes"]
    assert operations["add-import"]["targets"] == ["module"]
    assert operations["add-import"]["required_arguments"] == ["file", "statement"]
    assert "IMPORT_ALREADY_EXISTS" in operations["add-import"]["possible_error_codes"]
    assert operations["add-decorator"]["targets"] == ["function", "method", "class"]
    assert operations["add-decorator"]["required_arguments"] == [
        "file",
        "symbol",
        "decorator",
        "position",
    ]
    assert "DECORATOR_ALREADY_EXISTS" in operations["add-decorator"]["possible_error_codes"]
    assert operations["remove-decorator"]["targets"] == ["function", "method", "class"]
    assert operations["remove-decorator"]["required_arguments"] == [
        "file",
        "symbol",
        "expect-decorator",
        "expect-position",
    ]
    assert "DECORATOR_NOT_FOUND" in operations["remove-decorator"]["possible_error_codes"]
    assert "DECORATOR_POSITION_MISMATCH" in operations["remove-decorator"]["possible_error_codes"]
    assert operations["remove-import"]["targets"] == ["module"]
    assert operations["remove-import"]["required_arguments"] == ["file", "expect-statement"]
    assert "IMPORT_NOT_FOUND" in operations["remove-import"]["possible_error_codes"]
    assert "IMPORT_AMBIGUOUS" in operations["remove-import"]["possible_error_codes"]
    assert "IMPORT_SCOPE_UNSUPPORTED" in operations["remove-import"]["possible_error_codes"]
    commands = {command["name"]: command for command in payload["commands"]}
    assert set(commands) == {"rollback"}
    assert commands["rollback"]["selectors"] == ["last", "id"]
    assert commands["rollback"]["mutually_exclusive_selectors"] is True
    assert "OPERATION_ID_INVALID" in commands["rollback"]["possible_error_codes"]


def test_capabilities_text_is_human_readable(capsys) -> None:
    exit_code = main(["capabilities"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "add-docstring" in output
    assert "remove-docstring" in output
    assert "add-return-type" in output
    assert "remove-return-type" in output
    assert "remove-parameter-type" in output
    assert "add-parameter-type" in output
    assert "add-import" in output
    assert "add-decorator" in output
    assert "remove-import" in output
    assert "rollback" in output


def test_capabilities_json_is_deterministic() -> None:
    assert serialize_capabilities("json") == serialize_capabilities("json")


def test_python_m_surepython_propagates_exit_code() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "surepython", "capabilities", "--format", "xml"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "invalid choice" in completed.stderr.lower()
