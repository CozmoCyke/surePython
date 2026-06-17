from __future__ import annotations

import base64
import dataclasses
import difflib
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from .codemods import (
    add_decorator,
    _decode_python_bytes,
    add_docstring,
    add_import,
    add_parameter_type,
    add_return_type,
    remove_decorator,
    remove_docstring,
    remove_import,
    remove_parameter_type,
    remove_return_type,
)
from .datasette_log import (
    PlanFileRecord,
    PlanRecord,
    PlanStepRecord,
    insert_plan_bundle,
    now_utc_iso,
    read_last_plan,
    read_plan_by_id,
    read_plan_files,
    read_plan_steps,
    read_rollback_for_source_plan,
)
from .git_tools import GitError, ensure_clean_git_repo, ensure_git_context, is_within_root, run_git, sha256_file
from .transaction_lock import acquire_project_mutation_lock


PLAN_SCHEMA_VERSION = "1.0"
TRANSACTION_MANIFEST_SCHEMA_VERSION = "1.0"
PLAN_MAX_STEPS = 50
INCOMPLETE_TRANSACTION_STATUSES = {
    "preparing",
    "writing",
    "testing",
    "logging",
    "restoring",
    "recovery_required",
}
TERMINAL_TRANSACTION_STATUSES = {"complete", "failed", "recovered"}
TRANSACTION_MANIFEST_ALLOWED_STATUSES = INCOMPLETE_TRANSACTION_STATUSES | TERMINAL_TRANSACTION_STATUSES
TRANSACTION_MANIFEST_INITIAL_STATUSES = {"preparing", "restoring"}
TRANSACTION_MANIFEST_TRANSITIONS = {
    None: TRANSACTION_MANIFEST_INITIAL_STATUSES,
    "preparing": {"writing", "failed", "recovery_required", "recovered"},
    "writing": {"testing", "logging", "restoring", "failed", "recovery_required", "recovered"},
    "testing": {"logging", "restoring", "failed", "recovery_required", "recovered"},
    "logging": {"complete", "restoring", "failed", "recovery_required", "recovered"},
    "restoring": {"failed", "recovery_required", "recovered", "logging"},
    "failed": {"recovered", "recovery_required"},
    "recovery_required": {"recovered", "failed"},
    "recovered": set(),
    "complete": set(),
}
SUPPORTED_PLAN_OPERATIONS = {
    "add-docstring",
    "remove-docstring",
    "add-return-type",
    "remove-return-type",
    "add-parameter-type",
    "remove-parameter-type",
    "add-import",
    "remove-import",
    "add-decorator",
    "remove-decorator",
}
PLAN_ALLOWED_ROOT_KEYS = {
    "plan_schema_version",
    "name",
    "description",
    "client_plan_id",
    "metadata",
    "steps",
}
PLAN_ALLOWED_STEP_KEYS = {
    "id",
    "operation",
    "file",
    "arguments",
}


@dataclass(frozen=True)
class PlanStepSpec:
    id: str
    operation: str
    file: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class PlanSpec:
    plan_schema_version: str
    steps: list[PlanStepSpec]
    name: str | None = None
    description: str | None = None
    client_plan_id: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class PlanStepPreview:
    index: int
    id: str
    operation: str
    file: str
    status: str
    diff: str
    before_sha256: str
    after_sha256: str
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None


@dataclass(frozen=True)
class PlanFilePreview:
    file: str
    before_sha256: str
    after_sha256: str
    final_diff: str


@dataclass(frozen=True)
class PlanSimulation:
    spec: PlanSpec
    project_root: Path
    preview_hash: str
    step_count: int
    file_count: int
    steps: list[PlanStepPreview]
    files: list[PlanFilePreview]
    final_diff: str
    before_bytes_by_file: dict[str, bytes]
    after_bytes_by_file: dict[str, bytes]


@dataclass(frozen=True)
class PlanPreviewResult:
    plan_schema_version: str
    name: str | None
    description: str | None
    client_plan_id: str | None
    metadata: dict[str, Any] | None
    preview_hash: str
    step_count: int
    file_count: int
    written: bool
    logged: bool
    tested: bool
    rollback_available: bool
    steps: list[dict[str, Any]]
    files: list[dict[str, Any]]
    final_diff: str
    plan_operation_id: int | None = None
    plan_uuid: str | None = None


@dataclass(frozen=True)
class PlanApplyResult:
    plan_schema_version: str
    name: str | None
    description: str | None
    client_plan_id: str | None
    metadata: dict[str, Any] | None
    preview_hash: str
    step_count: int
    file_count: int
    written: bool
    logged: bool
    tested: bool
    rollback_available: bool
    steps: list[dict[str, Any]]
    files: list[dict[str, Any]]
    final_diff: str
    plan_operation_id: int | None
    plan_uuid: str | None
    pytest_command: str | None
    pytest_exit_code: int | None
    pytest_status: str | None
    status: str
    message: str


@dataclass(frozen=True)
class PlanRollbackResult:
    plan_schema_version: str
    plan_operation_id: int | None
    rollback_plan_operation_id: int | None
    source_plan_operation_id: int | None
    plan_uuid: str | None
    preview_hash: str | None
    written: bool
    logged: bool
    tested: bool
    rollback_available: bool
    bytes_equal: bool
    status: str
    message: str
    steps: list[dict[str, Any]]
    files: list[dict[str, Any]]
    final_diff: str


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    if dataclasses.is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_relpath(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _validate_plan_structure(data: dict[str, Any]) -> PlanSpec:
    if not isinstance(data, dict):
        raise GitError("Plan file must contain a JSON object", code="PLAN_INVALID_JSON")
    if "plan_schema_version" not in data:
        raise GitError("Plan schema version is required", code="PLAN_INVALID")
    if data["plan_schema_version"] != PLAN_SCHEMA_VERSION:
        raise GitError("Unsupported plan schema version", code="PLAN_SCHEMA_UNSUPPORTED")
    if "steps" not in data:
        raise GitError("Plan steps are required", code="PLAN_INVALID")
    unexpected_root = set(data) - PLAN_ALLOWED_ROOT_KEYS
    if unexpected_root:
        raise GitError("Plan contains unknown top-level keys", code="PLAN_INVALID")
    steps_data = data["steps"]
    if not isinstance(steps_data, list):
        raise GitError("Plan steps must be a list", code="PLAN_INVALID")
    if len(steps_data) == 0:
        raise GitError("Plan must contain at least one step", code="PLAN_EMPTY")
    if len(steps_data) > PLAN_MAX_STEPS:
        raise GitError("Plan exceeds the maximum number of steps", code="PLAN_TOO_LARGE")

    seen_ids: set[str] = set()
    steps: list[PlanStepSpec] = []
    for index, item in enumerate(steps_data):
        if not isinstance(item, dict):
            raise GitError("Plan step must be a JSON object", code="PLAN_INVALID")
        unexpected_step = set(item) - PLAN_ALLOWED_STEP_KEYS
        if unexpected_step:
            raise GitError("Plan step contains unknown keys", code="PLAN_INVALID")
        step_id = item.get("id")
        operation = item.get("operation")
        file_name = item.get("file")
        arguments = item.get("arguments")
        if not isinstance(step_id, str) or not step_id.strip():
            raise GitError("Plan step id is required", code="PLAN_INVALID")
        if step_id in seen_ids:
            raise GitError("Plan step id must be unique", code="PLAN_DUPLICATE_STEP_ID")
        seen_ids.add(step_id)
        if not isinstance(operation, str) or not operation.strip():
            raise GitError("Plan step operation is required", code="PLAN_INVALID")
        if operation not in SUPPORTED_PLAN_OPERATIONS:
            raise GitError("Plan step operation is not supported", code="PLAN_OPERATION_UNSUPPORTED")
        if not isinstance(file_name, str) or not file_name.strip():
            raise GitError("Plan step file is required", code="PLAN_INVALID")
        if Path(file_name).is_absolute() or ".." in Path(file_name).parts:
            raise GitError("Plan step file path must be relative to the project", code="PLAN_ARGUMENTS_INVALID")
        if not isinstance(arguments, dict):
            raise GitError("Plan step arguments must be a JSON object", code="PLAN_ARGUMENTS_INVALID")
        steps.append(PlanStepSpec(id=step_id, operation=operation, file=file_name, arguments=arguments))

    metadata = data.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        raise GitError("Plan metadata must be a JSON object", code="PLAN_INVALID")

    return PlanSpec(
        plan_schema_version=str(data["plan_schema_version"]),
        name=data.get("name"),
        description=data.get("description"),
        client_plan_id=data.get("client_plan_id"),
        metadata=metadata,
        steps=steps,
    )


def load_plan_spec(plan_path: Path) -> PlanSpec:
    try:
        data = json.loads(plan_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GitError("Plan file does not exist", code="PLAN_FILE_NOT_FOUND") from exc
    except json.JSONDecodeError as exc:
        raise GitError("Plan file is not valid JSON", code="PLAN_INVALID_JSON") from exc
    return _validate_plan_structure(data)


def _required_arguments_for_operation(operation: str) -> set[str]:
    mapping = {
        "add-docstring": {"symbol", "docstring"},
        "remove-docstring": {"symbol", "expect_docstring"},
        "add-return-type": {"symbol", "annotation"},
        "remove-return-type": {"symbol", "expect_annotation"},
        "add-parameter-type": {"symbol", "parameter", "annotation"},
        "remove-parameter-type": {"symbol", "parameter", "expect_annotation"},
        "add-import": {"statement"},
        "remove-import": {"expect_statement"},
        "add-decorator": {"symbol", "decorator", "position"},
        "remove-decorator": {"symbol", "expect_decorator", "expect_position"},
    }
    return mapping[operation]


def _validate_step_arguments(operation: str, arguments: dict[str, Any]) -> None:
    required = _required_arguments_for_operation(operation)
    if set(arguments) != required:
        raise GitError("Plan step arguments do not match the supported codemod contract", code="PLAN_ARGUMENTS_INVALID")


def _copy_project_tree(source_root: Path, target_root: Path) -> None:
    ignored_names = {
        ".git",
        ".surepython",
        ".tmp",
        ".pytest_cache",
        ".venv",
        "__pycache__",
    }

    def _ignore(_directory: str, names: list[str]) -> set[str]:
        return {name for name in names if name in ignored_names}

    shutil.copytree(source_root, target_root, ignore=_ignore, dirs_exist_ok=True)


def _git_config_identity(root: Path) -> None:
    run_git(["config", "user.email", "surepython@example.com"], cwd=root)
    run_git(["config", "user.name", "SurePython"], cwd=root)


def _git_commit_all(root: Path, message: str) -> None:
    run_git(["add", "."], cwd=root)
    run_git(["commit", "--allow-empty", "-m", message], cwd=root)


def _git_commit_exists(root: Path) -> bool:
    try:
        run_git(["rev-parse", "--verify", "HEAD"], cwd=root)
    except GitError:
        return False
    return True


def _git_diff_text(root: Path, base: str, head: str) -> tuple[str, str]:
    stat = run_git(["diff", "--stat", base, head], cwd=root)
    diff = run_git(["diff", base, head], cwd=root)
    return stat, diff


def _operation_executor(operation: str) -> tuple[Callable[..., Any], dict[str, Any]]:
    mapping: dict[str, tuple[Callable[..., Any], dict[str, Any]]] = {
        "add-docstring": (add_docstring, {"symbol": "target"}),
        "remove-docstring": (remove_docstring, {"symbol": "target", "expect_docstring": "expect_docstring"}),
        "add-return-type": (add_return_type, {"symbol": "target", "annotation": "annotation"}),
        "remove-return-type": (remove_return_type, {"symbol": "target", "expect_annotation": "expect_annotation"}),
        "add-parameter-type": (
            add_parameter_type,
            {"symbol": "target", "parameter": "parameter", "annotation": "annotation"},
        ),
        "remove-parameter-type": (
            remove_parameter_type,
            {"symbol": "target", "parameter": "parameter", "expect_annotation": "expect_annotation"},
        ),
        "add-import": (add_import, {"statement": "statement"}),
        "remove-import": (remove_import, {"expect_statement": "expect_statement"}),
        "add-decorator": (
            add_decorator,
            {"symbol": "target", "decorator": "decorator", "position": "position"},
        ),
        "remove-decorator": (
            remove_decorator,
            {"symbol": "target", "expect_decorator": "expect_decorator", "expect_position": "expect_position"},
        ),
    }
    return mapping[operation]


def _call_operation(
    operation: str,
    file_path: Path,
    arguments: dict[str, Any],
    *,
    project_root: Path,
    db_path: Path | None,
    run_tests: bool,
    dry_run: bool,
) -> Any:
    executor, _ = _operation_executor(operation)
    kwargs: dict[str, Any] = {
        "project_root": project_root,
        "db_path": db_path,
        "run_tests": run_tests,
        "dry_run": dry_run,
    }
    if operation == "add-docstring":
        return executor(file_path, arguments["symbol"], **kwargs)
    if operation == "remove-docstring":
        return executor(file_path, arguments["symbol"], arguments["expect_docstring"], **kwargs)
    if operation == "add-return-type":
        return executor(file_path, arguments["symbol"], arguments["annotation"], **kwargs)
    if operation == "remove-return-type":
        return executor(file_path, arguments["symbol"], arguments["expect_annotation"], **kwargs)
    if operation == "add-parameter-type":
        return executor(
            file_path,
            arguments["symbol"],
            arguments["parameter"],
            arguments["annotation"],
            **kwargs,
        )
    if operation == "remove-parameter-type":
        return executor(
            file_path,
            arguments["symbol"],
            arguments["parameter"],
            arguments["expect_annotation"],
            **kwargs,
        )
    if operation == "add-import":
        return executor(file_path, arguments["statement"], **kwargs)
    if operation == "remove-import":
        return executor(file_path, arguments["expect_statement"], **kwargs)
    if operation == "add-decorator":
        return executor(
            file_path,
            arguments["symbol"],
            arguments["decorator"],
            arguments["position"],
            **kwargs,
        )
    if operation == "remove-decorator":
        return executor(
            file_path,
            arguments["symbol"],
            arguments["expect_decorator"],
            arguments["expect_position"],
            **kwargs,
        )
    raise GitError("Unsupported plan operation", code="PLAN_OPERATION_UNSUPPORTED")


def _simulate_plan(plan_spec: PlanSpec, project_root: Path) -> PlanSimulation:
    project_root = project_root.resolve()
    if not is_within_root(project_root, project_root):
        raise GitError("Invalid project root", code="PLAN_INVALID")

    before_bytes_by_file: dict[str, bytes] = {}
    for step in plan_spec.steps:
        step_path = (project_root / step.file).resolve()
        if not step_path.exists():
            raise GitError("Plan file not found", code="PLAN_FILE_NOT_FOUND", details={"file": step.file})
        if not is_within_root(step_path, project_root):
            raise GitError("Plan file is outside the project", code="FILE_OUTSIDE_PROJECT")
        before_bytes_by_file.setdefault(_normalize_relpath(step_path, project_root), step_path.read_bytes())

    staging_root = Path(tempfile.mkdtemp(prefix="surepython-plan-"))
    try:
        _copy_project_tree(project_root, staging_root)
        run_git(["init"], cwd=staging_root)
        _git_config_identity(staging_root)
        _git_commit_all(staging_root, "baseline")

        temp_state_file = (
            Path(tempfile.gettempdir())
            / "surepython"
            / "plan-state"
            / f"{staging_root.name}.json"
        )
        temp_state_file.parent.mkdir(parents=True, exist_ok=True)
        previous_state_file = os.environ.get("SUREPYTHON_STATE_FILE")
        os.environ["SUREPYTHON_STATE_FILE"] = str(temp_state_file)
        try:
            step_results: list[PlanStepPreview] = []
            for index, step in enumerate(plan_spec.steps):
                _validate_step_arguments(step.operation, step.arguments)
                temp_file = staging_root / step.file
                before_sha256 = sha256_file(temp_file)
                try:
                    result = _call_operation(
                        step.operation,
                        temp_file,
                        step.arguments,
                        project_root=staging_root,
                        db_path=None,
                        run_tests=False,
                        dry_run=False,
                    )
                except GitError as exc:
                    raise GitError(
                        "Plan step failed",
                        code="PLAN_STEP_FAILED",
                        details={
                            "failed_step_index": index,
                            "failed_step_id": step.id,
                            "failed_operation": step.operation,
                            "error": exc.to_payload(),
                        },
                    ) from exc
                _git_commit_all(staging_root, f"plan-step {step.id}")
                after_sha256 = sha256_file(temp_file)
                diff_text = _git_diff_text(staging_root, "HEAD~1", "HEAD")[1]
                step_results.append(
                    PlanStepPreview(
                        index=index,
                        id=step.id,
                        operation=step.operation,
                        file=step.file,
                        status="previewed",
                        diff=diff_text.rstrip("\n"),
                        before_sha256=before_sha256,
                        after_sha256=after_sha256,
                        result=_jsonable(result),
                        error=None,
                    )
                )

            after_bytes_by_file: dict[str, bytes] = {}
            for step in plan_spec.steps:
                rel = _normalize_relpath(staging_root / step.file, staging_root)
                after_bytes_by_file[rel] = (staging_root / step.file).read_bytes()

            file_results: list[PlanFilePreview] = []
            for rel_path, before_bytes in before_bytes_by_file.items():
                after_bytes = after_bytes_by_file[rel_path]
                before_sha256 = _hash_bytes(before_bytes)
                after_sha256 = _hash_bytes(after_bytes)
                file_results.append(
                    PlanFilePreview(
                        file=rel_path,
                        before_sha256=before_sha256,
                        after_sha256=after_sha256,
                        final_diff="",
                    )
                )

            baseline = "HEAD~" + str(len(plan_spec.steps)) if len(plan_spec.steps) > 0 else "HEAD"
            final_diff = _git_diff_text(staging_root, "HEAD~1", "HEAD")[1] if len(plan_spec.steps) == 1 else run_git(["diff", "HEAD~" + str(len(plan_spec.steps)), "HEAD"], cwd=staging_root)
            preview_hash = _build_preview_hash(plan_spec, before_bytes_by_file, after_bytes_by_file)
            for item in file_results:
                item = item
            return PlanSimulation(
                spec=plan_spec,
                project_root=project_root,
                preview_hash=preview_hash,
                step_count=len(plan_spec.steps),
                file_count=len(after_bytes_by_file),
                steps=step_results,
                files=[
                    PlanFilePreview(
                        file=rel,
                        before_sha256=_hash_bytes(before_bytes_by_file[rel]),
                        after_sha256=_hash_bytes(after_bytes_by_file[rel]),
                        final_diff="",
                    )
                    for rel in sorted(after_bytes_by_file)
                ],
                final_diff=run_git(["diff", "HEAD~" + str(len(plan_spec.steps)), "HEAD"], cwd=staging_root).rstrip("\n")
                if len(plan_spec.steps) > 0
                else "",
                before_bytes_by_file=before_bytes_by_file,
                after_bytes_by_file=after_bytes_by_file,
            )
        finally:
            if previous_state_file is None:
                os.environ.pop("SUREPYTHON_STATE_FILE", None)
            else:
                os.environ["SUREPYTHON_STATE_FILE"] = previous_state_file
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)


def _build_preview_hash(
    plan_spec: PlanSpec,
    before_bytes_by_file: dict[str, bytes],
    after_bytes_by_file: dict[str, bytes],
) -> str:
    canonical = {
        "plan_schema_version": plan_spec.plan_schema_version,
        "name": plan_spec.name,
        "description": plan_spec.description,
        "client_plan_id": plan_spec.client_plan_id,
        "metadata": plan_spec.metadata,
        "steps": [
            {
                "id": step.id,
                "operation": step.operation,
                "file": Path(step.file).as_posix(),
                "arguments": step.arguments,
            }
            for step in plan_spec.steps
        ],
        "files": [
            {
                "file": file_name,
                "before_sha256": _hash_bytes(before_bytes_by_file[file_name]),
                "after_sha256": _hash_bytes(after_bytes_by_file[file_name]),
            }
            for file_name in sorted(after_bytes_by_file)
        ],
    }
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def preview_plan(plan_path: Path, *, project_root: Path | None = None) -> PlanPreviewResult:
    plan_spec = load_plan_spec(plan_path)
    context = ensure_git_context(project_root or Path.cwd())
    context = ensure_clean_git_repo(context.root)
    with acquire_project_mutation_lock(context.root, "plan preview"):
        simulation = _simulate_plan(plan_spec, context.root)
    return PlanPreviewResult(
        plan_schema_version=plan_spec.plan_schema_version,
        name=plan_spec.name,
        description=plan_spec.description,
        client_plan_id=plan_spec.client_plan_id,
        metadata=plan_spec.metadata,
        preview_hash=simulation.preview_hash,
        step_count=simulation.step_count,
        file_count=simulation.file_count,
        written=False,
        logged=False,
        tested=False,
        rollback_available=False,
        steps=[_jsonable(step) for step in simulation.steps],
        files=[_jsonable(file_result) for file_result in simulation.files],
        final_diff=simulation.final_diff,
    )


def _inject_plan_fault(checkpoint: str) -> None:
    requested = os.environ.get("SUREPYTHON_PLAN_FAULT_AT")
    if not requested:
        return
    checkpoints = {item.strip() for item in requested.split(",") if item.strip()}
    if checkpoint not in checkpoints:
        return
    mode = os.environ.get("SUREPYTHON_PLAN_FAULT_MODE", "exception")
    details = {"checkpoint": checkpoint, "mode": mode}
    if mode == "exit":  # pragma: no cover - exercised by subprocess smokes
        os._exit(91)
    raise GitError("Injected transactional plan fault", code="PLAN_DATABASE_FAILED", details=details)


def _transaction_root(project_root: Path) -> Path:
    project_digest = hashlib.sha256(str(project_root.resolve()).encode("utf-8")).hexdigest()
    return Path(tempfile.gettempdir()) / "surepython" / "transactions" / project_digest


def _manifest_path(project_root: Path, transaction_uuid: str) -> Path:
    return _transaction_root(project_root) / transaction_uuid / "manifest.json"


def _manifest_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    payload = dict(manifest)
    payload.setdefault("transaction_manifest_schema_version", TRANSACTION_MANIFEST_SCHEMA_VERSION)
    payload.pop("manifest_payload_sha256", None)
    return payload


def _manifest_payload_sha256(manifest: dict[str, Any]) -> str:
    payload = json.dumps(
        _manifest_payload(manifest),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def _validate_manifest_structure(manifest: dict[str, Any], *, strict: bool = True) -> None:
    if not isinstance(manifest, dict):
        raise GitError("Manifest must be a JSON object", code="PLAN_MANIFEST_INVALID")
    for required_key in ("transaction_uuid", "project_root", "preview_hash", "status", "files"):
        if required_key not in manifest:
            raise GitError("Manifest is missing required fields", code="PLAN_MANIFEST_INVALID")
    if not isinstance(manifest.get("files"), list):
        raise GitError("Manifest files must be a list", code="PLAN_MANIFEST_INVALID")
    status = manifest.get("status")
    if status not in TRANSACTION_MANIFEST_ALLOWED_STATUSES:
        raise GitError("Unsupported transaction manifest state", code="PLAN_STATE_INVALID")
    schema_version = manifest.get("transaction_manifest_schema_version")
    expected = manifest.get("manifest_payload_sha256")
    if schema_version is None and expected is None:
        if strict:
            return
        return
    if schema_version != TRANSACTION_MANIFEST_SCHEMA_VERSION:
        raise GitError("Unsupported transaction manifest schema version", code="PLAN_MANIFEST_INVALID")
    if not isinstance(expected, str) or not expected.startswith("sha256:"):
        raise GitError("Manifest checksum is missing", code="PLAN_MANIFEST_INVALID")
    if _manifest_payload_sha256(manifest) != expected:
        raise GitError("Manifest checksum does not match", code="PLAN_MANIFEST_INVALID")


def _validate_manifest_transition(previous_status: str | None, next_status: str) -> None:
    if previous_status == next_status:
        return
    allowed = TRANSACTION_MANIFEST_TRANSITIONS.get(previous_status)
    if allowed is None or next_status not in allowed:
        raise GitError(
            "Transaction manifest state transition is not allowed",
            code="PLAN_STATE_INVALID",
            details={"previous_status": previous_status, "next_status": next_status},
        )


def _write_manifest(project_root: Path, manifest: dict[str, Any]) -> Path:
    transaction_uuid = manifest["transaction_uuid"]
    manifest_path = _manifest_path(project_root, transaction_uuid)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest["transaction_manifest_schema_version"] = TRANSACTION_MANIFEST_SCHEMA_VERSION
    manifest["manifest_payload_sha256"] = _manifest_payload_sha256(manifest)
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        _validate_manifest_structure(previous, strict=False)
        _validate_manifest_transition(previous.get("status"), manifest["status"])
    temp_path = manifest_path.with_name(manifest_path.name + ".tmp")
    temp_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temp_path, manifest_path)
    return manifest_path


def _read_manifest(project_root: Path, transaction_uuid: str) -> dict[str, Any]:
    manifest_path = _manifest_path(project_root, transaction_uuid)
    if not manifest_path.exists():
        raise GitError("Recovery manifest not found", code="PLAN_RECOVERY_REQUIRED")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _validate_manifest_structure(manifest, strict=False)
    return manifest


def _find_incomplete_manifest(project_root: Path) -> dict[str, Any] | None:
    root = _transaction_root(project_root)
    if not root.exists():
        return None
    found: dict[str, Any] | None = None
    for manifest_path in sorted(root.glob("*/manifest.json")):
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            raise GitError("Transaction manifest is invalid", code="PLAN_MANIFEST_INVALID")
        _validate_manifest_structure(data, strict=False)
        if data.get("status") in INCOMPLETE_TRANSACTION_STATUSES:
            if found is not None:
                raise GitError("Multiple incomplete transaction manifests were found", code="PLAN_RECOVERY_CONFLICT")
            found = data
            found["manifest_path"] = str(manifest_path)
    return found


def _ensure_no_recovery_required(project_root: Path) -> None:
    manifest = _find_incomplete_manifest(project_root)
    if manifest is not None:
        raise GitError("Plan recovery is required", code="PLAN_RECOVERY_REQUIRED")


def _write_actual_files(
    project_root: Path,
    after_bytes_by_file: dict[str, bytes],
    before_bytes_by_file: dict[str, bytes],
    manifest: dict[str, Any],
) -> None:
    manifest_path = _manifest_path(project_root, manifest["transaction_uuid"])
    transaction_dir = manifest_path.parent
    preimages_dir = transaction_dir / "preimages"
    manifest["status"] = "writing"
    _write_manifest(project_root, manifest)
    for rel_path, backup in before_bytes_by_file.items():
        preimage_path = preimages_dir / rel_path
        preimage_path.parent.mkdir(parents=True, exist_ok=True)
        preimage_path.write_bytes(backup)
    for rel_path, final_bytes in after_bytes_by_file.items():
        target = project_root / rel_path
        temp_path = target.with_name(target.name + ".surepython.tmp")
        temp_path.write_bytes(final_bytes)
        try:
            os.replace(temp_path, target)
        except Exception:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            raise
        _inject_plan_fault("apply:file-written")


def _restore_preimages(project_root: Path, before_bytes_by_file: dict[str, bytes], manifest: dict[str, Any]) -> bool:
    manifest["status"] = "restoring"
    _write_manifest(project_root, manifest)
    restored = True
    for rel_path, original_bytes in before_bytes_by_file.items():
        target = project_root / rel_path
        try:
            target.write_bytes(original_bytes)
        except Exception:
            restored = False
            break
        _inject_plan_fault("rollback:file-restored")
    if restored:
        for rel_path, original_bytes in before_bytes_by_file.items():
            if sha256_file(project_root / rel_path) != _hash_bytes(original_bytes):
                restored = False
                break
    return restored


def apply_plan(
    plan_path: Path,
    expected_preview_hash: str,
    *,
    project_root: Path | None = None,
    db_path: Path | None = None,
    run_tests: bool = False,
) -> PlanApplyResult:
    if db_path is None:
        raise GitError("Plan apply requires --db", code="DATABASE_ERROR")
    if not expected_preview_hash:
        raise GitError("Plan apply requires a preview hash", code="PLAN_PREVIEW_HASH_REQUIRED")
    plan_spec = load_plan_spec(plan_path)
    context = ensure_git_context(project_root or Path.cwd())
    _ensure_no_recovery_required(context.root)
    context = ensure_clean_git_repo(context.root)
    simulation = _simulate_plan(plan_spec, context.root)
    if simulation.preview_hash != expected_preview_hash:
        raise GitError(
            "Plan preview hash does not match the current project state",
            code="PLAN_PREVIEW_MISMATCH",
            details={
                "expected_preview_hash": expected_preview_hash,
                "actual_preview_hash": simulation.preview_hash,
            },
        )
    if simulation.final_diff.strip() == "":
        raise GitError("Plan has no final changes", code="PLAN_NO_FINAL_CHANGES")

    transaction_uuid = str(uuid.uuid4())
    manifest = {
        "transaction_uuid": transaction_uuid,
        "project_root": str(context.root),
        "plan_path": str(plan_path.resolve()),
        "plan_hash": _hash_text(plan_path.read_text(encoding="utf-8")),
        "preview_hash": simulation.preview_hash,
        "status": "preparing",
        "files": [],
    }
    _write_manifest(context.root, manifest)
    _inject_plan_fault("apply:manifest-written")

    before_bytes_by_file = simulation.before_bytes_by_file
    after_bytes_by_file = simulation.after_bytes_by_file
    files_state = []
    for rel_path in sorted(after_bytes_by_file):
        files_state.append(
            {
                "file": rel_path,
                "before_sha256": _hash_bytes(before_bytes_by_file[rel_path]),
                "after_sha256": _hash_bytes(after_bytes_by_file[rel_path]),
            }
        )
    manifest["files"] = files_state

    try:
        _write_actual_files(context.root, after_bytes_by_file, before_bytes_by_file, manifest)
        _inject_plan_fault("apply:files-written")
        if run_tests:
            manifest["status"] = "testing"
            _write_manifest(context.root, manifest)
        tests_command = f"{os.sys.executable} -m pytest" if run_tests else None
        tests_exit_code = None
        tests_status = None
        if run_tests:
            completed = subprocess.run(
                [os.sys.executable, "-m", "pytest"],
                cwd=str(context.root),
                check=False,
                capture_output=True,
                text=True,
            )
            tests_exit_code = completed.returncode
            tests_status = "passed" if completed.returncode == 0 else "failed"
            if completed.returncode != 0:
                manifest["status"] = "restoring"
                _restore_preimages(context.root, before_bytes_by_file, manifest)
                manifest["status"] = "failed"
                _write_manifest(context.root, manifest)
                raise GitError(
                    "pytest exited with a non-zero status",
                    code="PLAN_TESTS_FAILED",
                    details={"exit_code": completed.returncode},
                )
            _inject_plan_fault("apply:tests-passed")

        manifest["status"] = "logging"
        _write_manifest(context.root, manifest)
        plan_id = _insert_plan_bundle(
            db_path,
            plan_spec,
            context.root,
            simulation,
            plan_path=plan_path,
            transaction_uuid=transaction_uuid,
            tests_requested=run_tests,
            tests_passed=tests_exit_code == 0 if run_tests else None,
            tests_command=tests_command,
            tests_exit_code=tests_exit_code,
            tests_status=tests_status,
            status="tested" if run_tests else "applied",
            message="Applied transactional plan" if not run_tests else "Applied transactional plan and ran tests",
        )
        _inject_plan_fault("apply:db-committed")
    except GitError:
        raise
    except Exception as exc:
        manifest["status"] = "restoring"
        restored = _restore_preimages(context.root, before_bytes_by_file, manifest)
        manifest["status"] = "recovery_required" if not restored else "failed"
        _write_manifest(context.root, manifest)
        raise GitError(str(exc), code="PLAN_DATABASE_FAILED") from exc

    manifest["status"] = "complete"
    _write_manifest(context.root, manifest)
    _inject_plan_fault("apply:complete")
    return PlanApplyResult(
        plan_schema_version=plan_spec.plan_schema_version,
        name=plan_spec.name,
        description=plan_spec.description,
        client_plan_id=plan_spec.client_plan_id,
        metadata=plan_spec.metadata,
        preview_hash=simulation.preview_hash,
        step_count=simulation.step_count,
        file_count=simulation.file_count,
        written=True,
        logged=True,
        tested=run_tests,
        rollback_available=True,
        steps=[_jsonable(step) for step in simulation.steps],
        files=[_jsonable(file_result) for file_result in simulation.files],
        final_diff=simulation.final_diff,
        plan_operation_id=plan_id,
        plan_uuid=transaction_uuid,
        pytest_command=tests_command,
        pytest_exit_code=tests_exit_code,
        pytest_status=tests_status,
        status="tested" if run_tests else "applied",
        message="Applied transactional plan" if not run_tests else "Applied transactional plan and ran tests",
    )


def _insert_plan_bundle(
    db_path: Path | None,
    plan_spec: PlanSpec,
    project_root: Path,
    simulation: PlanSimulation,
    *,
    plan_path: Path | None,
    transaction_uuid: str,
    tests_requested: bool,
    tests_passed: bool | None,
    tests_command: str | None,
    tests_exit_code: int | None,
    tests_status: str | None,
    status: str,
    message: str,
) -> int:
    if db_path is None:
        return 0

    plan_record = PlanRecord(
        created_at=now_utc_iso(),
        plan_uuid=transaction_uuid,
        client_plan_id=plan_spec.client_plan_id,
        name=plan_spec.name,
        description=plan_spec.description,
        project_path=str(project_root),
        plan_schema_version=plan_spec.plan_schema_version,
        plan_path=str(plan_path.resolve()) if plan_path is not None else None,
        metadata_json=json.dumps(plan_spec.metadata, sort_keys=True, ensure_ascii=False) if plan_spec.metadata is not None else None,
        preview_hash=simulation.preview_hash,
        status=status,
        step_count=simulation.step_count,
        file_count=simulation.file_count,
        tests_requested=tests_requested,
        tests_passed=tests_passed,
        started_at=now_utc_iso(),
        completed_at=now_utc_iso(),
        error_code=None,
        rollback_of_plan_id=None,
        source_plan_id=None,
        message=message,
    )

    step_records = [
        PlanStepRecord(
            plan_id=0,
            step_index=step.index,
            step_id=step.id,
            operation=step.operation,
            file=step.file,
            arguments_json=json.dumps(plan_spec.steps[step.index].arguments, sort_keys=True, ensure_ascii=False),
            status="previewed",
            result_json=json.dumps(_jsonable(step.result), sort_keys=True, ensure_ascii=False) if step.result is not None else None,
            error_code=None,
            before_sha256=step.before_sha256,
            after_sha256=step.after_sha256,
        )
        for step in simulation.steps
    ]
    file_records = [
        PlanFileRecord(
            plan_id=0,
            file=file_result.file,
            before_sha256=file_result.before_sha256,
            after_sha256=file_result.after_sha256,
            before_bytes=simulation.before_bytes_by_file[file_result.file],
            after_bytes=simulation.after_bytes_by_file[file_result.file],
            restored=False,
        )
        for file_result in simulation.files
    ]
    return insert_plan_bundle(db_path, plan_record, step_records, file_records)


def _plan_result_from_db(
    plan_id: int,
    *,
    db_path: Path,
    project_root: Path,
    preview_hash: str | None = None,
    status: str = "rolled_back",
    message: str = "Rolled back transactional plan.",
    wrote: bool = True,
) -> PlanRollbackResult:
    plan_row = read_plan_by_id(db_path, plan_id)
    if plan_row is None:
        raise GitError("Plan not found", code="PLAN_NOT_FOUND")
    step_rows = read_plan_steps(db_path, plan_id)
    file_rows = read_plan_files(db_path, plan_id)
    return PlanRollbackResult(
        plan_schema_version=str(plan_row.plan_schema_version),
        plan_operation_id=plan_id,
        rollback_plan_operation_id=plan_id,
        source_plan_operation_id=plan_id,
        plan_uuid=plan_row.plan_uuid,
        preview_hash=preview_hash,
        written=wrote,
        logged=True,
        tested=False,
        rollback_available=False,
        bytes_equal=True,
        status=status,
        message=message,
        steps=[_jsonable(step) for step in step_rows],
        files=[_jsonable(file_row) for file_row in file_rows],
        final_diff="",
    )


def rollback_plan(
    db_path: Path,
    *,
    plan_id: int | None = None,
    last: bool = False,
    project_root: Path | None = None,
    dry_run: bool = False,
) -> PlanRollbackResult:
    root = ensure_git_context(project_root or Path.cwd()).root
    _ensure_no_recovery_required(root)
    root = ensure_clean_git_repo(root).root
    if plan_id is None and not last:
        raise GitError("plan rollback requires --last or --id", code="PLAN_INVALID")
    if plan_id is not None and last:
        raise GitError("plan rollback selectors are mutually exclusive", code="ROLLBACK_SELECTOR_CONFLICT")
    if plan_id is not None and plan_id <= 0:
        raise GitError("Plan id must be positive", code="OPERATION_ID_INVALID")
    if last:
        plan_row = read_last_plan(db_path)
    else:
        plan_row = read_plan_by_id(db_path, plan_id or 0)
    if plan_row is None:
        raise GitError("Plan not found", code="PLAN_NOT_FOUND")
    if plan_row.project_path and Path(plan_row.project_path).resolve() != root.resolve():
        raise GitError("Plan belongs to a different project", code="PROJECT_MISMATCH")
    if plan_row.status == "rolled_back" or plan_row.rollback_of_plan_id is not None:
        raise GitError("Plan has already been rolled back", code="PLAN_ALREADY_ROLLED_BACK")
    if read_rollback_for_source_plan(db_path, plan_row.id) is not None:
        raise GitError("Plan has already been rolled back", code="PLAN_ALREADY_ROLLED_BACK")

    files = read_plan_files(db_path, plan_row.id)
    if not files:
        raise GitError("Plan rollback not available", code="PLAN_ROLLBACK_FAILED")

    before_bytes_by_file = {row.file: row.before_bytes for row in files}
    after_bytes_by_file = {row.file: row.after_bytes for row in files}
    for row in files:
        current = (root / row.file).read_bytes()
        if _hash_bytes(current) != row.after_sha256:
            raise GitError("Current file hash does not match plan after_sha256", code="HASH_MISMATCH")

    preview_diff_chunks: list[str] = []
    for row in files:
        current_text = (root / row.file).read_text(encoding="utf-8")
        restored_text, _, _ = _decode_python_bytes(before_bytes_by_file[row.file])
        preview_diff_chunks.append(
            "".join(
                difflib.unified_diff(
                    current_text.splitlines(keepends=True),
                    restored_text.splitlines(keepends=True),
                    fromfile=str(root / row.file),
                    tofile=str(root / row.file),
                )
            ).rstrip("\n")
        )
    preview_diff = "\n".join(chunk for chunk in preview_diff_chunks if chunk).rstrip("\n")

    if dry_run:
        return PlanRollbackResult(
            plan_schema_version=plan_row.plan_schema_version,
            plan_operation_id=None,
            rollback_plan_operation_id=None,
            source_plan_operation_id=plan_row.id,
            plan_uuid=plan_row.plan_uuid,
            preview_hash=plan_row.preview_hash,
            written=False,
            logged=False,
            tested=False,
            rollback_available=False,
            bytes_equal=True,
            status="preview",
            message=f"Planned rollback of transactional plan {plan_row.id}.",
            steps=[
                {
                    "id": step.step_id,
                    "index": step.step_index,
                    "operation": step.operation,
                    "file": step.file,
                    "status": step.status,
                    "before_sha256": step.before_sha256,
                    "after_sha256": step.after_sha256,
                }
                for step in read_plan_steps(db_path, plan_row.id)
            ],
            files=[
                {
                    "file": row.file,
                    "before_sha256": row.before_sha256,
                    "after_sha256": row.after_sha256,
                    "restored_sha256": row.before_sha256,
                }
                for row in files
            ],
            final_diff=preview_diff,
        )

    manifest = {
        "transaction_uuid": str(uuid.uuid4()),
        "project_root": str(root),
        "plan_id": plan_row.id,
        "preview_hash": plan_row.preview_hash,
        "status": "restoring",
        "files": [
            {
                "file": row.file,
                "before_sha256": row.before_sha256,
                "after_sha256": row.after_sha256,
            }
            for row in files
        ],
    }
    _write_manifest(root, manifest)
    _inject_plan_fault("rollback:manifest-written")
    restored_ok = _restore_preimages(root, before_bytes_by_file, manifest)
    if not restored_ok:
        manifest["status"] = "recovery_required"
        _write_manifest(root, manifest)
        raise GitError("Plan rollback failed", code="PLAN_ROLLBACK_FAILED")
    _inject_plan_fault("rollback:files-restored")

    try:
        manifest["status"] = "logging"
        _write_manifest(root, manifest)
        rollback_row_id = insert_plan_bundle(
            db_path,
            PlanRecord(
                created_at=now_utc_iso(),
                project_path=plan_row.project_path,
                plan_uuid=str(uuid.uuid4()),
                client_plan_id=plan_row.client_plan_id,
                name=plan_row.name,
                description=plan_row.description,
                plan_schema_version=plan_row.plan_schema_version,
                plan_path=plan_row.plan_path,
                metadata_json=plan_row.metadata_json,
                preview_hash=plan_row.preview_hash,
                status="rolled_back",
                step_count=0,
                file_count=len(files),
                tests_requested=False,
                tests_passed=None,
                started_at=now_utc_iso(),
                completed_at=now_utc_iso(),
                error_code=None,
                rollback_of_plan_id=plan_row.id,
                source_plan_id=plan_row.id,
                message="Rolled back transactional plan.",
            ),
            [],
            [
                PlanFileRecord(
                    plan_id=0,
                    file=row.file,
                    before_sha256=row.after_sha256,
                    after_sha256=row.before_sha256,
                    before_bytes=row.after_bytes,
                    after_bytes=row.before_bytes,
                    restored=True,
                )
                for row in files
            ],
        )
        _inject_plan_fault("rollback:db-committed")
        manifest["status"] = "complete"
        _write_manifest(root, manifest)
        _inject_plan_fault("rollback:complete")
    except Exception as exc:
        manifest["status"] = "recovery_required"
        _write_manifest(root, manifest)
        raise GitError("Plan rollback failed", code="PLAN_ROLLBACK_FAILED") from exc

    original = _plan_result_from_db(plan_row.id, db_path=db_path, project_root=root, preview_hash=plan_row.preview_hash)
    return dataclasses.replace(
        original,
        rollback_plan_operation_id=rollback_row_id,
        source_plan_operation_id=plan_row.id,
        plan_operation_id=rollback_row_id,
        bytes_equal=True,
        status="rolled_back",
        message="Rolled back transactional plan.",
        written=True,
        final_diff=preview_diff,
    )


def recover_plan(*, project_root: Path | None = None) -> dict[str, Any]:
    root = ensure_git_context(project_root or Path.cwd()).root
    manifest = _find_incomplete_manifest(root)
    if manifest is None:
        return {"written": False, "recovered": False, "message": "No recovery required"}
    manifest_path = Path(manifest.get("manifest_path", _manifest_path(root, manifest["transaction_uuid"])))
    transaction_dir = manifest_path.parent
    preimages = transaction_dir / "preimages"
    restored = True
    _inject_plan_fault("recover:manifest-read")
    for file_info in manifest.get("files", []):
        target = root / file_info["file"]
        preimage_path = preimages / file_info["file"]
        if not preimage_path.exists():
            restored = False
            break
        target.write_bytes(preimage_path.read_bytes())
        if sha256_file(target) != file_info["before_sha256"]:
            restored = False
            break
        _inject_plan_fault("recover:file-restored")
    _inject_plan_fault("recover:files-restored")
    manifest["status"] = "recovered" if restored else "recovery_required"
    _write_manifest(root, manifest)
    _inject_plan_fault("recover:manifest-written")
    return {
        "written": restored,
        "recovered": restored,
        "transaction_uuid": manifest.get("transaction_uuid"),
        "status": manifest["status"],
    }
