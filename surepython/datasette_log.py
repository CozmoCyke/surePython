from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path


STATE_FILE_ENV = "SUREPYTHON_STATE_FILE"


@dataclass(frozen=True)
class OperationRecord:
    created_at: str
    project_path: str
    file_path: str
    operation: str
    symbol: str | None
    before_sha256: str | None
    after_sha256: str | None
    git_diff: str | None
    pytest_command: str | None
    pytest_exit_code: int | None
    pytest_status: str | None
    status: str
    message: str | None


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def state_file() -> Path:
    configured = os.environ.get(STATE_FILE_ENV)
    if configured:
        return Path(configured)
    return Path(tempfile.gettempdir()) / "surepython_last_operation.json"


def write_last_operation(record: OperationRecord) -> None:
    path = state_file()
    path.write_text(json.dumps(asdict(record), indent=2), encoding="utf-8")


def read_last_operation() -> OperationRecord:
    path = state_file()
    if not path.exists():
        raise FileNotFoundError("No recorded operation found")
    data = json.loads(path.read_text(encoding="utf-8"))
    return OperationRecord(**data)


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS surepython_operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            project_path TEXT NOT NULL,
            file_path TEXT NOT NULL,
            operation TEXT NOT NULL,
            symbol TEXT,
            before_sha256 TEXT,
            after_sha256 TEXT,
            git_diff TEXT,
            pytest_command TEXT,
            pytest_exit_code INTEGER,
            pytest_status TEXT,
            status TEXT NOT NULL,
            message TEXT
        )
        """
    )
    connection.commit()


def insert_record(db_path: Path, record: OperationRecord) -> None:
    connection = sqlite3.connect(str(db_path))
    try:
        ensure_schema(connection)
        connection.execute(
            """
            INSERT INTO surepython_operations (
                created_at,
                project_path,
                file_path,
                operation,
                symbol,
                before_sha256,
                after_sha256,
                git_diff,
                pytest_command,
                pytest_exit_code,
                pytest_status,
                status,
                message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.created_at,
                record.project_path,
                record.file_path,
                record.operation,
                record.symbol,
                record.before_sha256,
                record.after_sha256,
                record.git_diff,
                record.pytest_command,
                record.pytest_exit_code,
                record.pytest_status,
                record.status,
                record.message,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def read_last_supported_operation(db_path: Path) -> OperationRecord:
    if not db_path.exists():
        raise FileNotFoundError(f"Database does not exist: {db_path}")

    connection = sqlite3.connect(str(db_path))
    try:
        ensure_schema(connection)
        row = connection.execute(
            """
            SELECT
                created_at,
                project_path,
                file_path,
                operation,
                symbol,
                before_sha256,
                after_sha256,
                git_diff,
                pytest_command,
                pytest_exit_code,
                pytest_status,
                status,
                message
            FROM surepython_operations
            WHERE operation IN ('add-docstring', 'add-return-type')
              AND status IN ('applied', 'tested', 'failed')
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        raise FileNotFoundError("No applicable operation found")

    return OperationRecord(
        created_at=row[0],
        project_path=row[1],
        file_path=row[2],
        operation=row[3],
        symbol=row[4],
        before_sha256=row[5],
        after_sha256=row[6],
        git_diff=row[7],
        pytest_command=row[8],
        pytest_exit_code=row[9],
        pytest_status=row[10],
        status=row[11],
        message=row[12],
    )


def read_last_add_docstring_operation(db_path: Path) -> OperationRecord:
    record = read_last_supported_operation(db_path)
    if record.operation != "add-docstring":
        raise FileNotFoundError("No applicable add-docstring operation found")
    return record
