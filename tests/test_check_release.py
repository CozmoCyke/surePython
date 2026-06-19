from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath

import tools.check_release as check_release


def test_venv_python_uses_windows_layout(monkeypatch) -> None:
    monkeypatch.setattr(check_release.os, "name", "nt", raising=False)
    assert check_release._venv_python(PureWindowsPath("C:/tmp/venv")) == PureWindowsPath("C:/tmp/venv/Scripts/python.exe")


def test_venv_python_uses_posix_layout(monkeypatch) -> None:
    monkeypatch.setattr(check_release.os, "name", "posix", raising=False)
    assert check_release._venv_python(PurePosixPath("/tmp/venv")) == PurePosixPath("/tmp/venv/bin/python")
