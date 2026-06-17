from __future__ import annotations

import hashlib
import json
import os
import socket
import tempfile
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from .git_tools import GitError

LOCK_SCHEMA_VERSION = "1.0"

try:  # pragma: no cover - platform specific
    import fcntl  # type: ignore
except Exception:  # pragma: no cover - platform specific
    fcntl = None  # type: ignore[assignment]

try:  # pragma: no cover - platform specific
    import msvcrt  # type: ignore
except Exception:  # pragma: no cover - platform specific
    msvcrt = None  # type: ignore[assignment]


@dataclass
class _LockState:
    handle: Any
    lock_path: Path
    metadata_path: Path
    lock_uuid: str
    project_root: Path
    command: str
    acquired_at: str
    depth: int = 1


_LOCKS: dict[str, _LockState] = {}
_LOCKS_MUTEX = threading.Lock()


def project_lock_paths(project_root: Path) -> tuple[Path, Path]:
    digest = hashlib.sha256(str(project_root.resolve()).encode("utf-8")).hexdigest()
    base = Path(tempfile.gettempdir()) / "surepython" / "locks" / digest
    return base / "mutation.lock", base / "mutation.lock.json"


def _lock_file(handle: Any) -> None:
    if fcntl is not None:  # pragma: no cover - POSIX only
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return
    if msvcrt is not None:  # pragma: no cover - Windows only
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return
    raise GitError("Mutation locking is not supported on this platform", code="INTERNAL_ERROR")


def _unlock_file(handle: Any) -> None:
    if fcntl is not None:  # pragma: no cover - POSIX only
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return
    if msvcrt is not None:  # pragma: no cover - Windows only
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return


def _write_json_atomically(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temp_path, path)


@contextmanager
def acquire_project_mutation_lock(project_root: Path, command: str) -> Iterator[None]:
    root = project_root.resolve()
    lock_path, metadata_path = project_lock_paths(root)
    key = str(lock_path)

    nested = False
    with _LOCKS_MUTEX:
        state = _LOCKS.get(key)
        if state is not None:
            state.depth += 1
            nested = True

    if nested:
        try:
            yield
        finally:
            with _LOCKS_MUTEX:
                state = _LOCKS.get(key)
                if state is not None:
                    state.depth -= 1
        return

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
            try:  # pragma: no cover - best effort on Windows
                os.fsync(handle.fileno())
            except OSError:
                pass
        _lock_file(handle)
    except Exception as exc:
        handle.close()
        raise GitError(
            "Another SurePython process is already mutating this project",
            code="PROJECT_MUTATION_LOCKED",
            details={
                "project_root": str(root),
                "command": command,
                "lock_path": str(lock_path),
            },
        ) from exc

    state = _LockState(
        handle=handle,
        lock_path=lock_path,
        metadata_path=metadata_path,
        lock_uuid=str(uuid.uuid4()),
        project_root=root,
        command=command,
        acquired_at="",
    )
    try:
        from .datasette_log import now_utc_iso

        state.acquired_at = now_utc_iso()
        with _LOCKS_MUTEX:
            _LOCKS[key] = state
        _write_json_atomically(
            metadata_path,
            {
                "lock_schema_version": LOCK_SCHEMA_VERSION,
                "lock_uuid": state.lock_uuid,
                "pid": os.getpid(),
                "hostname": socket.gethostname(),
                "command": command,
                "project_root": str(root),
                "acquired_at": state.acquired_at,
                "status": "locked",
            },
        )
        yield
    finally:
        with _LOCKS_MUTEX:
            current = _LOCKS.get(key)
            if current is state:
                state.depth -= 1
                if state.depth <= 0:
                    _LOCKS.pop(key, None)
                    release_payload = {
                        "lock_schema_version": LOCK_SCHEMA_VERSION,
                        "lock_uuid": state.lock_uuid,
                        "pid": os.getpid(),
                        "hostname": socket.gethostname(),
                        "command": command,
                        "project_root": str(root),
                        "acquired_at": state.acquired_at,
                        "released_at": now_utc_iso(),
                        "status": "released",
                    }
                    try:
                        _write_json_atomically(metadata_path, release_payload)
                    except Exception:  # pragma: no cover - best effort release metadata
                        pass
                    finally:
                        try:
                            _unlock_file(handle)
                        finally:
                            handle.close()
