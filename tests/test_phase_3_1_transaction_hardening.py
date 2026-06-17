from __future__ import annotations

import json
import os
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from surepython.cli import main


REPO_ROOT = Path(__file__).resolve().parents[1]


def init_git_repo(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "user.email", "surepython@example.com"],
        cwd=str(root),
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "SurePython"],
        cwd=str(root),
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(["git", "add", "."], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "baseline"],
        cwd=str(root),
        check=True,
        capture_output=True,
        text=True,
    )


def git_status_short(root: Path) -> str:
    completed = subprocess.run(
        ["git", "status", "--short"],
        cwd=str(root),
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def commit_all(root: Path, message: str) -> None:
    subprocess.run(["git", "add", "."], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", message], cwd=str(root), check=True, capture_output=True, text=True)


def make_mutation_project(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "project"
    root.mkdir()
    (root / "service.py").write_text(
        "def run():\n"
        "    return 1\n",
        encoding="utf-8",
    )
    init_git_repo(root)
    return root, root / "service.py"


def make_plan_project(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "project"
    root.mkdir()
    (root / "module_a.py").write_text(
        "class Service:\n"
        "    def greet(self):\n"
        "        return 'hi'\n",
        encoding="utf-8",
    )
    (root / "module_b.py").write_text(
        "def load_user(source):\n"
        "    return source\n",
        encoding="utf-8",
    )
    tests_dir = root / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_smoke.py").write_text(
        "from module_a import Service\n"
        "from module_b import load_user\n\n"
        "def test_smoke():\n"
        "    assert Service().greet() == 'hi'\n"
        "    assert load_user('x') == 'x'\n",
        encoding="utf-8",
    )
    init_git_repo(root)
    plan = {
        "plan_schema_version": "1.0",
        "name": "hardening smoke",
        "steps": [
            {
                "id": "add-docstring",
                "operation": "add-docstring",
                "file": "module_a.py",
                "arguments": {"symbol": "Service.greet", "docstring": "Greet a user."},
            },
            {
                "id": "add-return",
                "operation": "add-return-type",
                "file": "module_b.py",
                "arguments": {"symbol": "load_user", "annotation": "str | None"},
            },
        ],
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    return root, plan_path, tmp_path / "plan.db"


def transaction_root(root: Path) -> Path:
    digest = hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()
    return Path(tempfile.gettempdir()) / "surepython" / "transactions" / digest


def _read_json(capsys) -> dict[str, object]:
    return json.loads(capsys.readouterr().out)


def test_mutation_lock_blocks_add_docstring_dry_run(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root, service = make_mutation_project(tmp_path)
    monkeypatch.chdir(root)

    helper = tmp_path / "hold_lock.py"
    helper.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "import time\n"
        "from surepython.transaction_lock import acquire_project_mutation_lock\n"
        "root = Path(sys.argv[1])\n"
        "with acquire_project_mutation_lock(root, 'lock-holder'):\n"
        "    print('locked', flush=True)\n"
        "    time.sleep(20)\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    proc = subprocess.Popen(
        [sys.executable, "-c", helper.read_text(encoding="utf-8"), str(root)],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert proc.stdout is not None
        assert proc.stdout.readline().strip() == "locked"

        exit_code = main(
            [
                "add-docstring",
                str(service),
                "--function",
                "run",
                "--dry-run",
                "--format",
                "json",
            ]
        )
        assert exit_code == 2
        payload = _read_json(capsys)
        assert payload["error"]["code"] == "PROJECT_MUTATION_LOCKED"
        assert git_status_short(root) == ""
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_plan_fault_injection_recovery_is_idempotent(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root, plan_path, db_path = make_plan_project(tmp_path)
    monkeypatch.chdir(root)

    preview_exit_code = main(["plan", "preview", str(plan_path), "--format", "json"])
    assert preview_exit_code == 0
    preview_hash = _read_json(capsys)["result"]["preview_hash"]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["SUREPYTHON_PLAN_FAULT_AT"] = "apply:file-written"
    env["SUREPYTHON_PLAN_FAULT_MODE"] = "exit"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "surepython",
            "plan",
            "apply",
            str(plan_path),
            "--expect-preview-hash",
            preview_hash,
            "--db",
            str(db_path),
            "--format",
            "json",
        ],
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 91
    assert (root / "module_a.py").exists()
    assert (root / "module_b.py").exists()

    apply_exit_code = main(
        [
            "plan",
            "apply",
            str(plan_path),
            "--expect-preview-hash",
            preview_hash,
            "--db",
            str(db_path),
            "--format",
            "json",
        ]
    )
    assert apply_exit_code == 4
    apply_payload = _read_json(capsys)
    assert apply_payload["error"]["code"] == "PLAN_RECOVERY_REQUIRED"

    recover_exit_code = main(["plan", "recover", "--format", "json"])
    assert recover_exit_code == 0
    recover_payload = _read_json(capsys)
    assert recover_payload["status"] == "recovered"
    assert recover_payload["result"]["recovered"] is True
    assert git_status_short(root) == ""

    second_recover_exit_code = main(["plan", "recover", "--format", "json"])
    assert second_recover_exit_code == 0
    second_recover_payload = _read_json(capsys)
    assert second_recover_payload["status"] == "noop"
    assert second_recover_payload["result"]["recovered"] is False


def test_atomic_mutation_refuses_while_plan_recovery_is_required(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root, plan_path, db_path = make_plan_project(tmp_path)
    monkeypatch.chdir(root)

    preview_exit_code = main(["plan", "preview", str(plan_path), "--format", "json"])
    assert preview_exit_code == 0
    preview_hash = _read_json(capsys)["result"]["preview_hash"]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["SUREPYTHON_PLAN_FAULT_AT"] = "apply:file-written"
    env["SUREPYTHON_PLAN_FAULT_MODE"] = "exit"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "surepython",
            "plan",
            "apply",
            str(plan_path),
            "--expect-preview-hash",
            preview_hash,
            "--db",
            str(db_path),
            "--format",
            "json",
        ],
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 91

    exit_code = main(
        [
            "add-docstring",
            str(root / "module_a.py"),
            "--function",
            "Service.greet",
            "--dry-run",
            "--format",
            "json",
        ]
    )
    assert exit_code == 4
    payload = _read_json(capsys)
    assert payload["error"]["code"] == "PLAN_RECOVERY_REQUIRED"


def test_plan_recover_reconciles_durable_sqlite_commit_without_restoring_files(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root, plan_path, db_path = make_plan_project(tmp_path)
    monkeypatch.chdir(root)

    preview_exit_code = main(["plan", "preview", str(plan_path), "--format", "json"])
    assert preview_exit_code == 0
    preview_hash = _read_json(capsys)["result"]["preview_hash"]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["SUREPYTHON_PLAN_FAULT_AT"] = "apply:db-committed"
    env["SUREPYTHON_PLAN_FAULT_MODE"] = "exit"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "surepython",
            "plan",
            "apply",
            str(plan_path),
            "--expect-preview-hash",
            preview_hash,
            "--db",
            str(db_path),
            "--format",
            "json",
        ],
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 91

    after_a = (root / "module_a.py").read_bytes()
    after_b = (root / "module_b.py").read_bytes()

    recover_exit_code = main(["plan", "recover", "--format", "json"])
    assert recover_exit_code == 0
    recover_payload = _read_json(capsys)
    assert recover_payload["status"] == "recovered"
    assert recover_payload["result"]["recovered"] is True
    assert recover_payload["result"]["written"] is False
    assert (root / "module_a.py").read_bytes() == after_a
    assert (root / "module_b.py").read_bytes() == after_b

    transaction_dir = transaction_root(root) / recover_payload["result"]["transaction_uuid"]
    assert not (transaction_dir / "preimages").exists()


def test_plan_recover_rejects_committed_sqlite_after_user_modification(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root, plan_path, db_path = make_plan_project(tmp_path)
    monkeypatch.chdir(root)

    preview_exit_code = main(["plan", "preview", str(plan_path), "--format", "json"])
    assert preview_exit_code == 0
    preview_hash = _read_json(capsys)["result"]["preview_hash"]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["SUREPYTHON_PLAN_FAULT_AT"] = "apply:db-committed"
    env["SUREPYTHON_PLAN_FAULT_MODE"] = "exit"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "surepython",
            "plan",
            "apply",
            str(plan_path),
            "--expect-preview-hash",
            preview_hash,
            "--db",
            str(db_path),
            "--format",
            "json",
        ],
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 91

    original_a = (root / "module_a.py").read_bytes()
    (root / "module_a.py").write_text(
        "class Service:\n"
        "    def greet(self):\n"
        "        return 'user edit'\n",
        encoding="utf-8",
    )

    recover_exit_code = main(["plan", "recover", "--format", "json"])
    assert recover_exit_code == 2
    recover_payload = _read_json(capsys)
    assert recover_payload["error"]["code"] == "PLAN_RECOVERY_CONFLICT"
    assert (root / "module_a.py").read_bytes() != original_a


def test_plan_manifest_integrity_rejects_invalid_state_and_checksum(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root, plan_path, db_path = make_plan_project(tmp_path)
    monkeypatch.chdir(root)

    preview_exit_code = main(["plan", "preview", str(plan_path), "--format", "json"])
    assert preview_exit_code == 0
    preview_hash = _read_json(capsys)["result"]["preview_hash"]

    manifest_root = transaction_root(root)
    legacy_dir = manifest_root / "legacy"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    (legacy_dir / "manifest.json").write_text(
        json.dumps(
            {
                "transaction_uuid": "legacy",
                "project_root": str(root),
                "plan_id": 1,
                "preview_hash": preview_hash,
                "status": "nonsense",
                "files": [],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    invalid_exit_code = main(["plan", "recover", "--format", "json"])
    assert invalid_exit_code == 2
    invalid_payload = _read_json(capsys)
    assert invalid_payload["error"]["code"] == "PLAN_STATE_INVALID"

    shutil.rmtree(legacy_dir, ignore_errors=True)
    legacy_dir2 = manifest_root / "checksum"
    legacy_dir2.mkdir(parents=True, exist_ok=True)
    (legacy_dir2 / "manifest.json").write_text(
        json.dumps(
            {
                "transaction_manifest_schema_version": "1.0",
                "transaction_uuid": "checksum",
                "project_root": str(root),
                "preview_hash": preview_hash,
                "status": "writing",
                "files": [],
                "manifest_payload_sha256": "sha256:" + "0" * 64,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    invalid_exit_code = main(["plan", "recover", "--format", "json"])
    assert invalid_exit_code == 4
    invalid_payload = _read_json(capsys)
    assert invalid_payload["error"]["code"] in {"PLAN_MANIFEST_INVALID", "PLAN_STATE_INVALID"}
