from __future__ import annotations

import json
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

import surepython
from surepython.package_resources import resource_text


ROOT = Path(__file__).resolve().parents[1]


def _pyproject() -> dict[str, object]:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_version_comes_from_pyproject() -> None:
    project = _pyproject()["project"]
    assert project["version"] == "0.17.0"
    assert surepython.__version__ == "0.17.0"


def test_runtime_dependencies_exclude_dev_tools() -> None:
    project = _pyproject()["project"]
    runtime = set(project["dependencies"])
    dev = set(project["optional-dependencies"]["dev"])
    assert runtime == {"libcst>=1.8", "tomli>=2; python_version < '3.11'"}
    assert {"build>=1.2", "pytest>=9.0", "twine>=6.0"} <= dev
    tomli_dependencies = [dependency for dependency in runtime if dependency.startswith("tomli")]
    assert len(tomli_dependencies) == 1
    assert "python_version" in tomli_dependencies[0]
    assert "3.11" in tomli_dependencies[0]
    assert all(not dependency.startswith("tomli") for dependency in dev)
    assert runtime.isdisjoint({"pytest>=9.0", "build>=1.2", "twine>=6.0"})


def test_packaged_contract_resources_are_available() -> None:
    payload = json.loads(resource_text("contracts", "public_contract_v1.json"))
    assert payload["contract_version"] == "1.0"
    assert json.loads(resource_text("contracts", "capabilities_v1.json"))["protocol_schema_version"] == "1.0"
    assert json.loads(resource_text("contracts", "plan_schema_v1.json"))["plan_schema_version"] == "1.0"


def test_gitignore_excludes_distribution_artifacts() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for token in ["dist/", "build/", "*.egg-info/", ".pytest_cache/", ".mypy_cache/", ".ruff_cache/", ".tmp/"]:
        assert token in gitignore

