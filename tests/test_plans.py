from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import tempfile
import uuid
from pathlib import Path

from surepython.cli import main


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


def commit_all(root: Path, message: str) -> None:
    subprocess.run(["git", "add", "."], cwd=str(root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", message], cwd=str(root), check=True, capture_output=True, text=True)


def git_status_short(root: Path) -> str:
    completed = subprocess.run(
        ["git", "status", "--short"],
        cwd=str(root),
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def make_sample_plan_project(tmp_path: Path) -> tuple[Path, Path, Path, bytes, bytes]:
    root = tmp_path / "project"
    root.mkdir()
    module_a = root / "module_a.py"
    module_b = root / "module_b.py"
    module_a.write_text(
        "class Service:\n"
        "    def greet(self):\n"
        "        return 'hi'\n",
        encoding="utf-8",
    )
    module_b.write_text(
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
    original_a = module_a.read_bytes()
    original_b = module_b.read_bytes()
    plan = {
        "plan_schema_version": "1.0",
        "name": "sample transactional plan",
        "description": "two-step surgical plan",
        "client_plan_id": "plan-001",
        "metadata": {"owner": "tests"},
        "steps": [
            {
                "id": "step-docstring",
                "operation": "add-docstring",
                "file": "module_a.py",
                "arguments": {
                    "symbol": "Service.greet",
                    "docstring": "Greet a user.",
                },
            },
            {
                "id": "step-return",
                "operation": "add-return-type",
                "file": "module_b.py",
                "arguments": {
                    "symbol": "load_user",
                    "annotation": "str | None",
                },
            },
        ],
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    return root, plan_path, tmp_path / "surepython.db", original_a, original_b


def read_plan_rows(db_path: Path) -> list[tuple]:
    with sqlite3.connect(str(db_path)) as connection:
        return connection.execute(
            """
            SELECT status, rollback_of_plan_id, source_plan_id, step_count, file_count
            FROM surepython_plans
            ORDER BY id
            """
        ).fetchall()


def plan_transaction_root(root: Path) -> Path:
    digest = hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()
    return Path(tempfile.gettempdir()) / "surepython" / "transactions" / digest


def test_plan_preview_json_is_structured_and_quiet(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root, plan_path, _db_path, original_a, original_b = make_sample_plan_project(tmp_path)
    monkeypatch.chdir(root)

    exit_code = main(["plan", "preview", str(plan_path), "--format", "json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["protocol_schema_version"] == "1.0"
    assert payload["command"] == "plan"
    assert payload["ok"] is True
    assert payload["status"] == "preview"
    assert payload["meta"] == {"action": "preview", "format": "json"}
    assert payload["result"]["written"] is False
    assert payload["result"]["logged"] is False
    assert payload["result"]["rollback_available"] is False
    assert payload["result"]["preview_hash"].startswith("sha256:")
    assert len(payload["result"]["steps"]) == 2
    assert len(payload["result"]["files"]) == 2
    assert payload["result"]["steps"][0]["operation"] == "add-docstring"
    assert payload["result"]["steps"][1]["operation"] == "add-return-type"
    assert (root / "module_a.py").read_bytes() == original_a
    assert (root / "module_b.py").read_bytes() == original_b
    assert git_status_short(root) == ""


def test_plan_apply_rollback_by_last_and_double_rollback_refusal(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root, plan_path, db_path, original_a, original_b = make_sample_plan_project(tmp_path)
    monkeypatch.chdir(root)

    preview_exit_code = main(["plan", "preview", str(plan_path), "--format", "json"])
    assert preview_exit_code == 0
    preview_payload = json.loads(capsys.readouterr().out)
    preview_hash = preview_payload["result"]["preview_hash"]

    apply_exit_code = main(
        [
            "plan",
            "apply",
            str(plan_path),
            "--expect-preview-hash",
            preview_hash,
            "--test",
            "--db",
            str(db_path),
            "--format",
            "json",
        ]
    )

    assert apply_exit_code == 0
    apply_payload = json.loads(capsys.readouterr().out)
    assert apply_payload["ok"] is True
    assert apply_payload["status"] == "tested"
    assert apply_payload["result"]["plan_operation_id"] is not None
    assert apply_payload["result"]["rollback_available"] is True
    assert apply_payload["result"]["tests"]["status"] == "passed"
    assert apply_payload["result"]["tests"]["exit_code"] == 0
    assert "TODO: Document this function." in (root / "module_a.py").read_text(encoding="utf-8")
    assert "-> str | None" in (root / "module_b.py").read_text(encoding="utf-8")
    assert git_status_short(root) != ""

    commit_all(root, "apply transactional plan")

    rollback_exit_code = main(["plan", "rollback", "--last", "--db", str(db_path), "--format", "json"])
    assert rollback_exit_code == 0
    rollback_payload = json.loads(capsys.readouterr().out)
    assert rollback_payload["ok"] is True
    assert rollback_payload["status"] == "rolled_back"
    assert rollback_payload["result"]["source_plan_operation_id"] == apply_payload["result"]["plan_operation_id"]
    assert rollback_payload["result"]["rollback_plan_operation_id"] is not None
    assert rollback_payload["result"]["bytes_equal"] is True
    assert (root / "module_a.py").read_bytes() == original_a
    assert (root / "module_b.py").read_bytes() == original_b

    commit_all(root, "restore transactional plan")

    second_exit_code = main(["plan", "rollback", "--last", "--db", str(db_path), "--format", "json"])
    assert second_exit_code == 2
    second_payload = json.loads(capsys.readouterr().out)
    assert second_payload["ok"] is False
    assert second_payload["status"] == "refused"
    assert second_payload["error"]["code"] == "PLAN_ALREADY_ROLLED_BACK"
    assert read_plan_rows(db_path) == [
        ("tested", None, None, 2, 2),
        ("rolled_back", apply_payload["result"]["plan_operation_id"], apply_payload["result"]["plan_operation_id"], 0, 2),
    ]
    assert git_status_short(root) == ""


def test_plan_apply_and_rollback_by_id_restores_bytes_and_logs(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root, plan_path, db_path, original_a, original_b = make_sample_plan_project(tmp_path)
    monkeypatch.chdir(root)

    preview_exit_code = main(["plan", "preview", str(plan_path), "--format", "json"])
    assert preview_exit_code == 0
    preview_hash = json.loads(capsys.readouterr().out)["result"]["preview_hash"]

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
    assert apply_exit_code == 0
    apply_payload = json.loads(capsys.readouterr().out)
    plan_operation_id = apply_payload["result"]["plan_operation_id"]
    commit_all(root, "apply transactional plan")

    rollback_exit_code = main(["plan", "rollback", "--id", str(plan_operation_id), "--db", str(db_path), "--format", "json"])
    assert rollback_exit_code == 0
    rollback_payload = json.loads(capsys.readouterr().out)
    rollback_operation_id = rollback_payload["result"]["rollback_plan_operation_id"]
    assert rollback_payload["result"]["source_plan_operation_id"] == plan_operation_id
    assert rollback_payload["result"]["rollback_plan_operation_id"] is not None
    assert rollback_payload["result"]["bytes_equal"] is True
    assert (root / "module_a.py").read_bytes() == original_a
    assert (root / "module_b.py").read_bytes() == original_b
    commit_all(root, "restore transactional plan")

    second_exit_code = main(["plan", "rollback", "--id", str(plan_operation_id), "--db", str(db_path), "--format", "json"])
    assert second_exit_code == 2
    second_payload = json.loads(capsys.readouterr().out)
    assert second_payload["error"]["code"] == "PLAN_ALREADY_ROLLED_BACK"
    assert read_plan_rows(db_path) == [
        ("applied", None, None, 2, 2),
        ("rolled_back", plan_operation_id, plan_operation_id, 0, 2),
    ]
    assert rollback_operation_id is not None
    assert git_status_short(root) == ""


def test_plan_preview_hash_mismatch_is_refused(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root, plan_path, db_path, _, _ = make_sample_plan_project(tmp_path)
    monkeypatch.chdir(root)

    exit_code = main(
        [
            "plan",
            "apply",
            str(plan_path),
            "--expect-preview-hash",
            "sha256:" + "0" * 64,
            "--db",
            str(db_path),
            "--format",
            "json",
        ]
    )

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "PLAN_PREVIEW_MISMATCH"
    assert git_status_short(root) == ""


def test_plan_recover_restores_preimages_without_git_changes(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SUREPYTHON_STATE_FILE", str(tmp_path / "state.json"))
    root, _plan_path, _db_path, original_a, original_b = make_sample_plan_project(tmp_path)
    transaction_dir = plan_transaction_root(root) / str(uuid.uuid4())
    preimages_dir = transaction_dir / "preimages"
    preimages_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "transaction_uuid": transaction_dir.name,
        "project_root": str(root),
        "plan_id": 1,
        "preview_hash": "sha256:" + "1" * 64,
        "status": "writing",
        "files": [
            {"file": "module_a.py", "before_sha256": hashlib.sha256(original_a).hexdigest(), "after_sha256": hashlib.sha256(b"changed a").hexdigest()},
            {"file": "module_b.py", "before_sha256": hashlib.sha256(original_b).hexdigest(), "after_sha256": hashlib.sha256(b"changed b").hexdigest()},
        ],
    }
    (transaction_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (preimages_dir / "module_a.py").parent.mkdir(parents=True, exist_ok=True)
    (preimages_dir / "module_a.py").write_bytes(original_a)
    (preimages_dir / "module_b.py").write_bytes(original_b)
    (root / "module_a.py").write_bytes(b"changed a")
    (root / "module_b.py").write_bytes(b"changed b")
    monkeypatch.chdir(root)

    exit_code = main(["plan", "recover", "--format", "json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["status"] == "recovered"
    assert payload["result"]["recovered"] is True
    assert (root / "module_a.py").read_bytes() == original_a
    assert (root / "module_b.py").read_bytes() == original_b
    assert git_status_short(root) == ""
