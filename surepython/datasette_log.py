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
    import_statement: str | None = None
    import_binding: str | None = None
    parameter: str | None = None
    operation_id: int | None = None
    source_operation_id: int | None = None


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
            import_statement TEXT,
            import_binding TEXT,
            parameter TEXT,
            before_sha256 TEXT,
            after_sha256 TEXT,
            git_diff TEXT,
            pytest_command TEXT,
            pytest_exit_code INTEGER,
            pytest_status TEXT,
            status TEXT NOT NULL,
            message TEXT,
            source_operation_id INTEGER
        )
        """
    )
    connection.commit()
    existing_columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(surepython_operations)").fetchall()
    }
    if "source_operation_id" not in existing_columns:
        connection.execute("ALTER TABLE surepython_operations ADD COLUMN source_operation_id INTEGER")
        connection.commit()
    if "parameter" not in existing_columns:
        connection.execute("ALTER TABLE surepython_operations ADD COLUMN parameter TEXT")
        connection.commit()
    if "import_statement" not in existing_columns:
        connection.execute("ALTER TABLE surepython_operations ADD COLUMN import_statement TEXT")
        connection.commit()
    if "import_binding" not in existing_columns:
        connection.execute("ALTER TABLE surepython_operations ADD COLUMN import_binding TEXT")
        connection.commit()

    connection.execute(
        """
        UPDATE surepython_operations
        SET source_operation_id = (
            SELECT prior.id
            FROM surepython_operations AS prior
            WHERE prior.id < surepython_operations.id
              AND prior.project_path = surepython_operations.project_path
              AND prior.file_path = surepython_operations.file_path
              AND prior.symbol = surepython_operations.symbol
              AND prior.operation != 'rollback'
              AND prior.status IN ('applied', 'tested', 'failed')
            ORDER BY prior.id DESC
            LIMIT 1
        )
        WHERE operation = 'rollback' AND source_operation_id IS NULL
        """
    )
    connection.commit()


def insert_record(db_path: Path, record: OperationRecord) -> int:
    connection = sqlite3.connect(str(db_path))
    try:
        ensure_schema(connection)
        cursor = connection.execute(
            """
            INSERT INTO surepython_operations (
                created_at,
                project_path,
                file_path,
                operation,
                symbol,
                import_statement,
                import_binding,
                parameter,
                before_sha256,
                after_sha256,
                git_diff,
                pytest_command,
                pytest_exit_code,
                pytest_status,
                status,
                message,
                source_operation_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.created_at,
                record.project_path,
                record.file_path,
                record.operation,
                record.symbol,
                record.import_statement,
                record.import_binding,
                record.parameter,
                record.before_sha256,
                record.after_sha256,
                record.git_diff,
                record.pytest_command,
                record.pytest_exit_code,
                record.pytest_status,
                record.status,
                record.message,
                record.source_operation_id,
            ),
        )
        connection.commit()
        return int(cursor.lastrowid)
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
                id,
                created_at,
                project_path,
                file_path,
                operation,
                symbol,
                import_statement,
                import_binding,
                parameter,
                before_sha256,
                after_sha256,
                git_diff,
                pytest_command,
                pytest_exit_code,
                pytest_status,
                status,
                message,
                source_operation_id
            FROM surepython_operations
            WHERE operation != 'rollback'
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
        operation_id=row[0],
        created_at=row[1],
        project_path=row[2],
        file_path=row[3],
        operation=row[4],
        symbol=row[5],
        import_statement=row[6],
        import_binding=row[7],
        parameter=row[8],
        before_sha256=row[9],
        after_sha256=row[10],
        git_diff=row[11],
        pytest_command=row[12],
        pytest_exit_code=row[13],
        pytest_status=row[14],
        status=row[15],
        message=row[16],
        source_operation_id=row[17],
    )


def read_last_add_docstring_operation(db_path: Path) -> OperationRecord:
    record = read_last_supported_operation(db_path)
    if record.operation != "add-docstring":
        raise FileNotFoundError("No applicable add-docstring operation found")
    return record


def read_operation_by_id(db_path: Path, operation_id: int) -> OperationRecord:
    if not db_path.exists():
        raise FileNotFoundError(f"Database does not exist: {db_path}")

    connection = sqlite3.connect(str(db_path))
    try:
        ensure_schema(connection)
        row = connection.execute(
            """
            SELECT
                id,
                created_at,
                project_path,
                file_path,
                operation,
                symbol,
                import_statement,
                import_binding,
                parameter,
                before_sha256,
                after_sha256,
                git_diff,
                pytest_command,
                pytest_exit_code,
                pytest_status,
                status,
                message,
                source_operation_id
            FROM surepython_operations
            WHERE id = ?
            """,
            (operation_id,),
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        raise FileNotFoundError(f"Operation not found: {operation_id}")

    return OperationRecord(
        operation_id=row[0],
        created_at=row[1],
        project_path=row[2],
        file_path=row[3],
        operation=row[4],
        symbol=row[5],
        import_statement=row[6],
        import_binding=row[7],
        parameter=row[8],
        before_sha256=row[9],
        after_sha256=row[10],
        git_diff=row[11],
        pytest_command=row[12],
        pytest_exit_code=row[13],
        pytest_status=row[14],
        status=row[15],
        message=row[16],
        source_operation_id=row[17],
    )


def read_rollback_for_source_operation(db_path: Path, source_operation_id: int) -> OperationRecord | None:
    if not db_path.exists():
        raise FileNotFoundError(f"Database does not exist: {db_path}")

    connection = sqlite3.connect(str(db_path))
    try:
        ensure_schema(connection)
        row = connection.execute(
            """
            SELECT
                id,
                created_at,
                project_path,
                file_path,
                operation,
                symbol,
                import_statement,
                import_binding,
                parameter,
                before_sha256,
                after_sha256,
                git_diff,
                pytest_command,
                pytest_exit_code,
                pytest_status,
                status,
                message,
                source_operation_id
            FROM surepython_operations
            WHERE operation = 'rollback'
              AND source_operation_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (source_operation_id,),
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        return None

    return OperationRecord(
        operation_id=row[0],
        created_at=row[1],
        project_path=row[2],
        file_path=row[3],
        operation=row[4],
        symbol=row[5],
        import_statement=row[6],
        import_binding=row[7],
        parameter=row[8],
        before_sha256=row[9],
        after_sha256=row[10],
        git_diff=row[11],
        pytest_command=row[12],
        pytest_exit_code=row[13],
        pytest_status=row[14],
        status=row[15],
        message=row[16],
        source_operation_id=row[17],
    )
