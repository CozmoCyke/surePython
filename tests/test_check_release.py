from __future__ import annotations

import tools.check_release as check_release


def test_venv_python_uses_windows_layout() -> None:
    assert check_release._venv_python_parts("nt") == ("Scripts", "python.exe")


def test_venv_python_uses_posix_layout() -> None:
    assert check_release._venv_python_parts("posix") == ("bin", "python")
