from __future__ import annotations

import subprocess

import tools.check_release as check_release


def test_venv_python_uses_windows_layout() -> None:
    assert check_release._venv_python_parts("nt") == ("Scripts", "python.exe")


def test_venv_python_uses_posix_layout() -> None:
    assert check_release._venv_python_parts("posix") == ("bin", "python")


def test_install_artifact_in_venv_installs_dependencies(monkeypatch) -> None:
    calls: list[tuple[list[str], dict[str, str] | None]] = []

    def fake_run(command: list[str], *, cwd=None, env=None):  # noqa: ANN001
        calls.append((command, env))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(check_release, "_run", fake_run)

    wheel = check_release.Path("surepython-0.17.0-py3-none-any.whl")
    sdist = check_release.Path("surepython-0.17.0.tar.gz")
    python = check_release.Path(r"C:\temp\venv\Scripts\python.exe")

    check_release._install_artifact_in_venv(wheel, python)
    check_release._install_artifact_in_venv(sdist, python)

    assert calls[0][0] == [str(python), "-m", "pip", "install", str(wheel)]
    assert calls[1][0] == [
        str(python),
        "-m",
        "pip",
        "install",
        "--no-build-isolation",
        str(sdist),
    ]
    assert calls[0][1] is None
    assert calls[1][1] == {
        "PYTHONPATH": str(check_release.CURRENT_SITE_PACKAGES),
        "PIP_NO_CACHE_DIR": "1",
    }
