"""SurePython package."""

from __future__ import annotations

from pathlib import Path
from importlib import metadata

__all__ = ["__version__"]


def _version_from_pyproject() -> str:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    if not pyproject.exists():
        raise RuntimeError("pyproject.toml is not available in the installed package")
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        if line.startswith("version = "):
            return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError("Unable to determine SurePython version from pyproject.toml")


try:
    __version__ = _version_from_pyproject()
except RuntimeError:
    try:
        __version__ = metadata.version("surepython")
    except metadata.PackageNotFoundError:
        raise
