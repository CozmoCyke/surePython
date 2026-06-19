from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile
from pathlib import Path
from typing import Any
import sysconfig


ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
BOOTSTRAP_DIR = ROOT / ".vendor3"
CURRENT_SITE_PACKAGES = Path(sysconfig.get_paths()["purelib"])
FORBIDDEN_PATTERNS = (
    ".git/",
    ".tmp/",
    "__pycache__/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
    ".venv/",
    ".deps/",
    ".vendor/",
    ".vendor3/",
)
DEFAULT_ENV = {
    "PYTHONUTF8": "1",
    "PYTHONIOENCODING": "utf-8",
}


def _run(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    merged_env.update(DEFAULT_ENV)
    pythonpath_parts = [str(BOOTSTRAP_DIR)] if BOOTSTRAP_DIR.exists() else []
    if pythonpath_parts:
        pythonpath = merged_env.get("PYTHONPATH")
        merged_env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts if pythonpath is None else pythonpath_parts + [pythonpath])
    if env is not None:
        merged_env.update(env)
    completed = subprocess.run(
        command,
        cwd=str(cwd or ROOT),
        env=merged_env,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed with exit code {completed.returncode}: {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return completed


def _json_pyproject() -> dict[str, Any]:
    import tomllib

    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _version_from_pyproject() -> str:
    return str(_json_pyproject()["project"]["version"])


def _ensure_clean_git() -> None:
    status = _run(["git", "status", "--short"])
    allowed = (".vendor3/", "sitecustomize.py")
    unexpected = [
        line
        for line in status.stdout.splitlines()
        if line.strip() and not any(token in line.replace("\\", "/") for token in allowed)
    ]
    if unexpected:
        raise RuntimeError(f"Worktree is not clean: {unexpected}")


def _ensure_version_consistency() -> None:
    from surepython import __version__

    version = _version_from_pyproject()
    if __version__ != version:
        raise RuntimeError(f"Package version mismatch: pyproject={version!r} surepython.__version__={__version__!r}")


def _build_artifacts(dist_dir: Path) -> tuple[Path, Path]:
    if importlib.util.find_spec("build") is None:
        raise RuntimeError("The build package is required. Install it with `python -m pip install build`.")
    dist_dir.mkdir(parents=True, exist_ok=True)
    for artifact in dist_dir.iterdir():
        if artifact.is_file():
            artifact.unlink()
    _run([sys.executable, "-m", "build", "--sdist", "--wheel", "--no-isolation", "--outdir", str(dist_dir)])
    wheels = sorted(dist_dir.glob("*.whl"))
    sdists = sorted(dist_dir.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise RuntimeError("Expected exactly one wheel and one sdist.")
    return wheels[0], sdists[0]


def _check_twine(dist_dir: Path) -> None:
    if importlib.util.find_spec("twine") is None:
        raise RuntimeError("The twine package is required. Install it with `python -m pip install twine`.")
    _run([sys.executable, "-m", "twine", "check", *sorted(str(path) for path in dist_dir.iterdir())])


def _wheel_members(wheel_path: Path) -> list[str]:
    with zipfile.ZipFile(wheel_path) as archive:
        return sorted(archive.namelist())


def _sdist_members(sdist_path: Path) -> list[str]:
    with tarfile.open(sdist_path, "r:gz") as archive:
        return sorted(member.name for member in archive.getmembers())


def _assert_contains(members: list[str], required: list[str], *, label: str) -> None:
    missing = [name for name in required if name not in members]
    if missing:
        raise RuntimeError(f"{label} is missing required files: {missing}")


def _assert_forbidden_absent(members: list[str], *, label: str) -> None:
    for member in members:
        if any(pattern in member.replace("\\", "/") for pattern in FORBIDDEN_PATTERNS):
            raise RuntimeError(f"{label} contains forbidden path: {member}")
        if member.startswith("tests/"):
            raise RuntimeError(f"{label} contains test file: {member}")
        if member.startswith(".github/"):
            raise RuntimeError(f"{label} contains repository-only workflow content: {member}")
        if member.endswith(".db") or member.endswith(".sqlite"):
            raise RuntimeError(f"{label} contains database artifact: {member}")
        if member.startswith("surepython/.pytest_cache/") or member.startswith("surepython/.tmp/"):
            raise RuntimeError(f"{label} contains local cache artifact: {member}")


def _inspect_wheel(wheel_path: Path) -> None:
    members = _wheel_members(wheel_path)
    _assert_contains(
        members,
        [
            "surepython/__init__.py",
            "surepython/__main__.py",
            "surepython/cli.py",
            "surepython/contracts/public_contract_v1.json",
            "surepython/contracts/cli_contract_v1.json",
            "surepython/contracts/capabilities_v1.json",
            "surepython/contracts/error_registry_v1.json",
            "surepython/contracts/protocol_envelope_v1.json",
            "surepython/contracts/plan_schema_v1.json",
            "surepython/contracts/sqlite_schema_v1.json",
            "surepython/contracts/fixtures/preview_hash_vectors.json",
            "surepython/contracts/golden/corpus.json",
            f"surepython-{_version_from_pyproject()}.dist-info/METADATA",
            f"surepython-{_version_from_pyproject()}.dist-info/WHEEL",
            f"surepython-{_version_from_pyproject()}.dist-info/entry_points.txt",
        ],
        label="wheel",
    )
    _assert_forbidden_absent(members, label="wheel")


def _inspect_sdist(sdist_path: Path) -> None:
    members = _sdist_members(sdist_path)
    _assert_contains(
        members,
        [
            f"surepython-{_version_from_pyproject()}/pyproject.toml",
            f"surepython-{_version_from_pyproject()}/README.md",
            f"surepython-{_version_from_pyproject()}/AGENTS.md",
            f"surepython-{_version_from_pyproject()}/surepython/cli.py",
            f"surepython-{_version_from_pyproject()}/surepython/contracts/public_contract_v1.json",
            f"surepython-{_version_from_pyproject()}/contracts/public_contract_v1.json",
        ],
        label="sdist",
    )
    _assert_forbidden_absent(members, label="sdist")


def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _create_venv(venv_dir: Path) -> Path:
    builder = venv.EnvBuilder(with_pip=True, clear=True)
    builder.create(venv_dir)
    return _venv_python(venv_dir)


def _run_installed_command(python: Path, cwd: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return _run([str(python), "-m", "surepython", *args], cwd=cwd, env=env)


def _run_shell_command(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return _run(command, cwd=cwd, env=env)


def _git(path: Path, *args: str) -> None:
    _run(["git", *args], cwd=path)


def _smoke_project(root: Path, name: str = "project") -> Path:
    project = root / name
    project.mkdir(parents=True, exist_ok=True)
    (project / "service.py").write_text(
        "def parse(source):\n    return source\n",
        encoding="utf-8",
        newline="\n",
    )
    (project / "plan.json").write_text(
        json.dumps(
            {
                "plan_schema_version": "1.0",
                "steps": [
                    {
                        "id": "add-docstring",
                        "operation": "add-docstring",
                        "file": "service.py",
                        "arguments": {
                            "symbol": "parse",
                            "docstring": "Parse a source.",
                        },
                    }
                ],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "SurePython"
    env["GIT_AUTHOR_EMAIL"] = "surepython@example.invalid"
    env["GIT_COMMITTER_NAME"] = "SurePython"
    env["GIT_COMMITTER_EMAIL"] = "surepython@example.invalid"
    _git(project, "init")
    _git(project, "add", ".")
    _run(["git", "commit", "-m", "Initial smoke project"], cwd=project, env=env)
    return project


def _smoke_installed_package(python: Path, *, label: str) -> None:
    with tempfile.TemporaryDirectory(prefix=f"surepython-{label}-") as temp_dir:
        temp_root = Path(temp_dir)
        project = _smoke_project(temp_root)
        venv_site = temp_root / "venv"
        venv_python = _create_venv(venv_site)
        install = _run([str(venv_python), "-m", "pip", "install", str(python.parent.parent)])
        # The install command above is not used; the caller passes the venv python.


def _install_artifact_in_venv(artifact: Path, venv_python: Path) -> None:
    if artifact.name.endswith(".tar.gz"):
        _run(
            [str(venv_python), "-m", "pip", "install", "--no-build-isolation", "--no-deps", str(artifact)],
            env={"PYTHONPATH": str(CURRENT_SITE_PACKAGES), "PIP_NO_CACHE_DIR": "1"},
        )
    else:
        _run([str(venv_python), "-m", "pip", "install", "--no-deps", str(artifact)])


def _smoke_run(venv_python: Path, project: Path) -> dict[str, Any]:
    db_path = project.parent / "smoke.db"
    original_bytes = (project / "service.py").read_bytes()
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "SurePython"
    env["GIT_AUTHOR_EMAIL"] = "surepython@example.invalid"
    env["GIT_COMMITTER_NAME"] = "SurePython"
    env["GIT_COMMITTER_EMAIL"] = "surepython@example.invalid"
    cap = _run_installed_command(venv_python, project, "capabilities", "--format", "json")
    if cap.returncode != 0:
        raise RuntimeError(f"capabilities failed: {cap.stderr}")
    scan = _run_installed_command(venv_python, project, "scan", str(project), "--format", "json")
    if scan.returncode != 0:
        raise RuntimeError(f"scan failed: {scan.stderr}")
    dry = _run_installed_command(
        venv_python,
        project,
        "add-docstring",
        "service.py",
        "--function",
        "parse",
        "--dry-run",
        "--format",
        "json",
    )
    if dry.returncode != 0:
        raise RuntimeError(f"add-docstring dry-run failed: {dry.stderr}")
    apply = _run_installed_command(
        venv_python,
        project,
        "add-docstring",
        "service.py",
        "--function",
        "parse",
        "--db",
        str(db_path),
        "--format",
        "json",
    )
    if apply.returncode != 0:
        raise RuntimeError(f"add-docstring apply failed: {apply.stderr}")
    payload = json.loads(apply.stdout)
    operation_id = payload["result"]["operation_id"]
    _run(["git", "add", "service.py"], cwd=project)
    _run(["git", "commit", "-m", "Applied smoke change"], cwd=project, env=env)
    rollback = _run_installed_command(
        venv_python,
        project,
        "rollback",
        "--id",
        str(operation_id),
        "--db",
        str(db_path),
        "--format",
        "json",
    )
    if rollback.returncode != 0:
        raise RuntimeError(f"rollback failed: {rollback.stderr}")
    if (project / "service.py").read_bytes() != original_bytes:
        raise RuntimeError("Rollback smoke did not restore the original bytes.")
    _run(["git", "restore", "service.py"], cwd=project)
    status = _run(["git", "status", "--short"], cwd=project)
    if status.stdout.strip():
        raise RuntimeError(f"Smoke project is not clean after restore: {status.stdout}")
    plan_project = _smoke_project(project.parent, "plan")
    plan = _run_installed_command(venv_python, plan_project, "plan", "preview", str(plan_project / "plan.json"), "--format", "json")
    if plan.returncode != 0:
        raise RuntimeError(f"plan preview failed: {plan.stderr}")
    return {
        "apply": payload,
        "rollback": json.loads(rollback.stdout),
        "plan": json.loads(plan.stdout),
    }


def _validate_installed_artifact(artifact: Path, *, label: str) -> None:
    with tempfile.TemporaryDirectory(prefix=f"surepython-release-{label}-") as temp_dir:
        temp_root = Path(temp_dir)
        venv_dir = temp_root / "venv"
        venv_python = _create_venv(venv_dir)
        _install_artifact_in_venv(artifact, venv_python)
        project = _smoke_project(temp_root, "project")
        for command in (
            [str(venv_python), "-m", "surepython", "--help"],
            [str(venv_python), "-m", "surepython", "capabilities", "--format", "json"],
        ):
            completed = _run_shell_command(command, cwd=project)
            if completed.returncode != 0:
                raise RuntimeError(
                    f"Installed smoke failed for {artifact.name}: {' '.join(command)}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
                )
        smoke = _smoke_run(venv_python, project)
        if not smoke["apply"]["result"]["operation_id"]:
            raise RuntimeError("Installed smoke did not yield an operation id.")
        if smoke["rollback"]["status"] != "rolled_back":
            raise RuntimeError("Rollback smoke did not report rolled_back.")
        surepython_path = _run(
            [
                str(venv_python),
                "-c",
                "import surepython; print(surepython.__file__)",
            ],
            cwd=project,
        ).stdout.strip()
        if "site-packages" not in surepython_path:
            raise RuntimeError(f"Installed import does not come from site-packages: {surepython_path}")
        uninstall = _run([str(venv_python), "-m", "pip", "uninstall", "-y", "surepython"], cwd=project)
        if uninstall.returncode != 0:
            raise RuntimeError(f"Uninstall failed: {uninstall.stderr}")
        after_uninstall = _run(
            [
                str(venv_python),
                "-c",
                "import importlib.util; import sys; sys.exit(0 if importlib.util.find_spec('surepython') is None else 1)",
            ],
            cwd=project,
        )
        if after_uninstall.returncode != 0:
            raise RuntimeError("surepython is still importable after uninstall.")


def check_release(dist_dir: Path = DIST_DIR) -> dict[str, Any]:
    _ensure_clean_git()
    _ensure_version_consistency()
    if not dist_dir.exists():
        dist_dir.mkdir(parents=True, exist_ok=True)
    wheel_path, sdist_path = _build_artifacts(dist_dir)
    _check_twine(dist_dir)
    _inspect_wheel(wheel_path)
    _inspect_sdist(sdist_path)
    _validate_installed_artifact(wheel_path, label="wheel")
    _validate_installed_artifact(sdist_path, label="sdist")
    return {
        "ok": True,
        "version": _version_from_pyproject(),
        "wheel": wheel_path.name,
        "sdist": sdist_path.name,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate SurePython release artifacts.")
    parser.add_argument("--dist-dir", default=str(DIST_DIR))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = check_release(Path(args.dist_dir))
    except Exception as exc:  # pragma: no cover - CLI wrapper
        print(f"RELEASE_CHECK_FAILED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI wrapper
    raise SystemExit(main())
