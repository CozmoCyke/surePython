"""Helpers for reading SurePython package resources."""

from __future__ import annotations

from importlib import resources


def resource_text(*parts: str) -> str:
    """Read a text resource shipped inside the installed package."""

    resource = resources.files("surepython")
    for part in parts:
        resource = resource.joinpath(part)
    return resource.read_text(encoding="utf-8")

