from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

from . import __version__ as SUREPYTHON_VERSION

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
    expected_import_statement: str | None = None
    removed_import_statement: str | None = None
    removed_import_binding: str | None = None
    import_match_count: int | None = None
    decorator_expression: str | None = None
    decorator_position: str | None = None
    decorator_target_kind: str | None = None
    expected_decorator_expression: str | None = None
    expected_decorator_position: str | None = None
    removed_decorator_expression: str | None = None
    removed_decorator_position: str | None = None
    parameter: str | None = None
    expected_return_annotation: str | None = None
    return_annotation: str | None = None
    operation_id: int | None = None
    source_operation_id: int | None = None
    target_kind: str | None = None
    parameter_kind: str | None = None
    expected_parameter_annotation: str | None = None
    parameter_annotation: str | None = None
    expected_docstring_text: str | None = None
    removed_docstring_text: str | None = None
    removed_docstring_source: str | None = None
    docstring_target_kind: str | None = None
    docstring_replacement_statement: str | None = None
    before_source_b64: str | None = None


@dataclass(frozen=True)
class PlanRecord:
    created_at: str
    project_path: str
    plan_uuid: str
    client_plan_id: str | None
    name: str | None
    description: str | None
    plan_schema_version: str
    preview_hash: str
    status: str
    step_count: int
    file_count: int
    tests_requested: bool
    tests_passed: bool | None
    started_at: str
    completed_at: str
    error_code: str | None
    rollback_of_plan_id: int | None
    source_plan_id: int | None
    message: str | None
    plan_path: str | None = None
    metadata_json: str | None = None
    id: int | None = None


@dataclass(frozen=True)
class PlanStepRecord:
    plan_id: int | None
    step_index: int
    step_id: str
    operation: str
    file: str
    arguments_json: str
    status: str
    result_json: str | None
    error_code: str | None
    before_sha256: str
    after_sha256: str
    id: int | None = None


@dataclass(frozen=True)
class PlanFileRecord:
    plan_id: int | None
    file: str
    before_sha256: str
    after_sha256: str
    before_bytes: bytes
    after_bytes: bytes
    restored: bool
    id: int | None = None


@dataclass(frozen=True)
class SchemaMetadataRecord:
    schema_version: str
    created_by_version: str
    last_migrated_by_version: str


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
            expected_import_statement TEXT,
            removed_import_statement TEXT,
            removed_import_binding TEXT,
            import_match_count INTEGER,
            decorator_expression TEXT,
            decorator_position TEXT,
            decorator_target_kind TEXT,
            expected_decorator_expression TEXT,
            expected_decorator_position TEXT,
            removed_decorator_expression TEXT,
            removed_decorator_position TEXT,
            parameter TEXT,
            expected_return_annotation TEXT,
            return_annotation TEXT,
            before_sha256 TEXT,
            after_sha256 TEXT,
            git_diff TEXT,
            pytest_command TEXT,
            pytest_exit_code INTEGER,
            pytest_status TEXT,
            status TEXT NOT NULL,
            message TEXT,
            source_operation_id INTEGER,
            target_kind TEXT,
            parameter_kind TEXT,
            expected_parameter_annotation TEXT,
            parameter_annotation TEXT,
            expected_docstring_text TEXT,
            removed_docstring_text TEXT,
            removed_docstring_source TEXT,
            docstring_target_kind TEXT,
            docstring_replacement_statement TEXT,
            before_source_b64 TEXT
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
    if "expected_import_statement" not in existing_columns:
        connection.execute("ALTER TABLE surepython_operations ADD COLUMN expected_import_statement TEXT")
        connection.commit()
    if "removed_import_statement" not in existing_columns:
        connection.execute("ALTER TABLE surepython_operations ADD COLUMN removed_import_statement TEXT")
        connection.commit()
    if "removed_import_binding" not in existing_columns:
        connection.execute("ALTER TABLE surepython_operations ADD COLUMN removed_import_binding TEXT")
        connection.commit()
    if "import_match_count" not in existing_columns:
        connection.execute("ALTER TABLE surepython_operations ADD COLUMN import_match_count INTEGER")
        connection.commit()
    if "decorator_expression" not in existing_columns:
        connection.execute("ALTER TABLE surepython_operations ADD COLUMN decorator_expression TEXT")
        connection.commit()
    if "decorator_position" not in existing_columns:
        connection.execute("ALTER TABLE surepython_operations ADD COLUMN decorator_position TEXT")
        connection.commit()
    if "decorator_target_kind" not in existing_columns:
        connection.execute("ALTER TABLE surepython_operations ADD COLUMN decorator_target_kind TEXT")
        connection.commit()
    if "expected_decorator_expression" not in existing_columns:
        connection.execute("ALTER TABLE surepython_operations ADD COLUMN expected_decorator_expression TEXT")
        connection.commit()
    if "expected_decorator_position" not in existing_columns:
        connection.execute("ALTER TABLE surepython_operations ADD COLUMN expected_decorator_position TEXT")
        connection.commit()
    if "removed_decorator_expression" not in existing_columns:
        connection.execute("ALTER TABLE surepython_operations ADD COLUMN removed_decorator_expression TEXT")
        connection.commit()
    if "removed_decorator_position" not in existing_columns:
        connection.execute("ALTER TABLE surepython_operations ADD COLUMN removed_decorator_position TEXT")
        connection.commit()
    if "expected_return_annotation" not in existing_columns:
        connection.execute(
            "ALTER TABLE surepython_operations ADD COLUMN expected_return_annotation TEXT"
        )
        connection.commit()
    if "return_annotation" not in existing_columns:
        connection.execute("ALTER TABLE surepython_operations ADD COLUMN return_annotation TEXT")
        connection.commit()
    if "target_kind" not in existing_columns:
        connection.execute("ALTER TABLE surepython_operations ADD COLUMN target_kind TEXT")
        connection.commit()
    if "parameter_kind" not in existing_columns:
        connection.execute("ALTER TABLE surepython_operations ADD COLUMN parameter_kind TEXT")
        connection.commit()
    if "expected_parameter_annotation" not in existing_columns:
        connection.execute(
            "ALTER TABLE surepython_operations ADD COLUMN expected_parameter_annotation TEXT"
        )
        connection.commit()
    if "parameter_annotation" not in existing_columns:
        connection.execute("ALTER TABLE surepython_operations ADD COLUMN parameter_annotation TEXT")
        connection.commit()
    if "expected_docstring_text" not in existing_columns:
        connection.execute(
            "ALTER TABLE surepython_operations ADD COLUMN expected_docstring_text TEXT"
        )
        connection.commit()
    if "removed_docstring_text" not in existing_columns:
        connection.execute(
            "ALTER TABLE surepython_operations ADD COLUMN removed_docstring_text TEXT"
        )
        connection.commit()
    if "removed_docstring_source" not in existing_columns:
        connection.execute(
            "ALTER TABLE surepython_operations ADD COLUMN removed_docstring_source TEXT"
        )
        connection.commit()
    if "docstring_target_kind" not in existing_columns:
        connection.execute(
            "ALTER TABLE surepython_operations ADD COLUMN docstring_target_kind TEXT"
        )
        connection.commit()
    if "docstring_replacement_statement" not in existing_columns:
        connection.execute(
            "ALTER TABLE surepython_operations ADD COLUMN docstring_replacement_statement TEXT"
        )
        connection.commit()
    if "before_source_b64" not in existing_columns:
        connection.execute("ALTER TABLE surepython_operations ADD COLUMN before_source_b64 TEXT")
        connection.commit()

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS surepython_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            project_path TEXT NOT NULL,
            plan_uuid TEXT NOT NULL,
            client_plan_id TEXT,
            name TEXT,
            description TEXT,
            plan_schema_version TEXT NOT NULL,
            plan_path TEXT,
            metadata_json TEXT,
            preview_hash TEXT NOT NULL,
            status TEXT NOT NULL,
            step_count INTEGER NOT NULL,
            file_count INTEGER NOT NULL,
            tests_requested INTEGER NOT NULL,
            tests_passed INTEGER,
            started_at TEXT NOT NULL,
            completed_at TEXT NOT NULL,
            error_code TEXT,
            rollback_of_plan_id INTEGER,
            source_plan_id INTEGER,
            message TEXT
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS surepython_plan_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            step_index INTEGER NOT NULL,
            step_id TEXT NOT NULL,
            operation TEXT NOT NULL,
            file TEXT NOT NULL,
            arguments_json TEXT NOT NULL,
            status TEXT NOT NULL,
            result_json TEXT,
            error_code TEXT,
            before_sha256 TEXT NOT NULL,
            after_sha256 TEXT NOT NULL,
            FOREIGN KEY(plan_id) REFERENCES surepython_plans(id)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS surepython_plan_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            file TEXT NOT NULL,
            before_sha256 TEXT NOT NULL,
            after_sha256 TEXT NOT NULL,
            before_bytes BLOB NOT NULL,
            after_bytes BLOB NOT NULL,
            restored INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(plan_id) REFERENCES surepython_plans(id)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS surepython_schema_metadata (
            schema_version TEXT NOT NULL,
            created_by_version TEXT NOT NULL,
            last_migrated_by_version TEXT NOT NULL
        )
        """
    )
    connection.commit()

    metadata_count = connection.execute("SELECT COUNT(*) FROM surepython_schema_metadata").fetchone()[0]
    if metadata_count == 0:
        connection.execute(
            """
            INSERT INTO surepython_schema_metadata (
                schema_version,
                created_by_version,
                last_migrated_by_version
            ) VALUES (?, ?, ?)
            """,
            ("1.0", SUREPYTHON_VERSION, SUREPYTHON_VERSION),
        )
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
                expected_import_statement,
                removed_import_statement,
                removed_import_binding,
                import_match_count,
                decorator_expression,
                decorator_position,
                decorator_target_kind,
                expected_decorator_expression,
                expected_decorator_position,
                removed_decorator_expression,
                removed_decorator_position,
                parameter,
                expected_return_annotation,
                return_annotation,
                before_sha256,
                after_sha256,
                git_diff,
                pytest_command,
                pytest_exit_code,
                pytest_status,
                status,
                message,
                source_operation_id,
                target_kind,
                parameter_kind,
                expected_parameter_annotation,
                parameter_annotation,
                expected_docstring_text,
                removed_docstring_text,
                removed_docstring_source,
                docstring_target_kind,
                docstring_replacement_statement,
                before_source_b64
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.created_at,
                record.project_path,
                record.file_path,
                record.operation,
                record.symbol,
                record.import_statement,
                record.import_binding,
                record.expected_import_statement,
                record.removed_import_statement,
                record.removed_import_binding,
                record.import_match_count,
                record.decorator_expression,
                record.decorator_position,
                record.decorator_target_kind,
                record.expected_decorator_expression,
                record.expected_decorator_position,
                record.removed_decorator_expression,
                record.removed_decorator_position,
                record.parameter,
                record.expected_return_annotation,
                record.return_annotation,
                record.before_sha256,
                record.after_sha256,
                record.git_diff,
                record.pytest_command,
                record.pytest_exit_code,
                record.pytest_status,
                record.status,
                record.message,
                record.source_operation_id,
                record.target_kind,
                record.parameter_kind,
                record.expected_parameter_annotation,
                record.parameter_annotation,
                record.expected_docstring_text,
                record.removed_docstring_text,
                record.removed_docstring_source,
                record.docstring_target_kind,
                record.docstring_replacement_statement,
                record.before_source_b64,
            ),
        )
        connection.commit()
        return int(cursor.lastrowid)
    finally:
        connection.close()


def _operation_record_from_row(row: tuple) -> OperationRecord:
    return OperationRecord(
        operation_id=row[0],
        created_at=row[1],
        project_path=row[2],
        file_path=row[3],
        operation=row[4],
        symbol=row[5],
        import_statement=row[6],
        import_binding=row[7],
        expected_import_statement=row[8],
        removed_import_statement=row[9],
        removed_import_binding=row[10],
        import_match_count=row[11],
        decorator_expression=row[12],
        decorator_position=row[13],
        decorator_target_kind=row[14],
        expected_decorator_expression=row[15],
        expected_decorator_position=row[16],
        removed_decorator_expression=row[17],
        removed_decorator_position=row[18],
        parameter=row[19],
        expected_return_annotation=row[20],
        return_annotation=row[21],
        before_sha256=row[22],
        after_sha256=row[23],
        git_diff=row[24],
        pytest_command=row[25],
        pytest_exit_code=row[26],
        pytest_status=row[27],
        status=row[28],
        message=row[29],
        source_operation_id=row[30],
        target_kind=row[31],
        parameter_kind=row[32],
        expected_parameter_annotation=row[33],
        parameter_annotation=row[34],
        expected_docstring_text=row[35],
        removed_docstring_text=row[36],
        removed_docstring_source=row[37],
        docstring_target_kind=row[38],
        docstring_replacement_statement=row[39],
        before_source_b64=row[40],
    )


def _plan_record_from_row(row: tuple) -> PlanRecord:
    return PlanRecord(
        id=row[0],
        created_at=row[1],
        project_path=row[2],
        plan_uuid=row[3],
        client_plan_id=row[4],
        name=row[5],
        description=row[6],
        plan_schema_version=row[7],
        plan_path=row[8],
        metadata_json=row[9],
        preview_hash=row[10],
        status=row[11],
        step_count=row[12],
        file_count=row[13],
        tests_requested=bool(row[14]),
        tests_passed=(None if row[15] is None else bool(row[15])),
        started_at=row[16],
        completed_at=row[17],
        error_code=row[18],
        rollback_of_plan_id=row[19],
        source_plan_id=row[20],
        message=row[21],
    )


def _plan_step_record_from_row(row: tuple) -> PlanStepRecord:
    return PlanStepRecord(
        id=row[0],
        plan_id=row[1],
        step_index=row[2],
        step_id=row[3],
        operation=row[4],
        file=row[5],
        arguments_json=row[6],
        status=row[7],
        result_json=row[8],
        error_code=row[9],
        before_sha256=row[10],
        after_sha256=row[11],
    )


def _plan_file_record_from_row(row: tuple) -> PlanFileRecord:
    return PlanFileRecord(
        id=row[0],
        plan_id=row[1],
        file=row[2],
        before_sha256=row[3],
        after_sha256=row[4],
        before_bytes=row[5],
        after_bytes=row[6],
        restored=bool(row[7]),
    )


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
                expected_import_statement,
                removed_import_statement,
                removed_import_binding,
                import_match_count,
                decorator_expression,
                decorator_position,
                decorator_target_kind,
                expected_decorator_expression,
                expected_decorator_position,
                removed_decorator_expression,
                removed_decorator_position,
                parameter,
                expected_return_annotation,
                return_annotation,
                before_sha256,
                after_sha256,
                git_diff,
                pytest_command,
                pytest_exit_code,
                pytest_status,
                status,
                message,
                source_operation_id,
                target_kind,
                parameter_kind,
                expected_parameter_annotation,
                parameter_annotation,
                expected_docstring_text,
                removed_docstring_text,
                removed_docstring_source,
                docstring_target_kind,
                docstring_replacement_statement,
                before_source_b64
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

    return _operation_record_from_row(row)


def read_last_plan(db_path: Path) -> PlanRecord:
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
                plan_uuid,
                client_plan_id,
                name,
                description,
                plan_schema_version,
                plan_path,
                metadata_json,
                preview_hash,
                status,
                step_count,
                file_count,
                tests_requested,
                tests_passed,
                started_at,
                completed_at,
                error_code,
                rollback_of_plan_id,
                source_plan_id,
                message
            FROM surepython_plans
            WHERE rollback_of_plan_id IS NULL
              AND status IN ('applied', 'tested', 'failed')
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        raise FileNotFoundError("No applicable plan found")

    return _plan_record_from_row(row)


def read_plan_by_id(db_path: Path, plan_id: int) -> PlanRecord:
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
                plan_uuid,
                client_plan_id,
                name,
                description,
                plan_schema_version,
                plan_path,
                metadata_json,
                preview_hash,
                status,
                step_count,
                file_count,
                tests_requested,
                tests_passed,
                started_at,
                completed_at,
                error_code,
                rollback_of_plan_id,
                source_plan_id,
                message
            FROM surepython_plans
            WHERE id = ?
            """,
            (plan_id,),
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        raise FileNotFoundError(f"Plan not found: {plan_id}")

    return _plan_record_from_row(row)


def read_plan_by_uuid(db_path: Path, plan_uuid: str) -> PlanRecord | None:
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
                plan_uuid,
                client_plan_id,
                name,
                description,
                plan_schema_version,
                plan_path,
                metadata_json,
                preview_hash,
                status,
                step_count,
                file_count,
                tests_requested,
                tests_passed,
                started_at,
                completed_at,
                error_code,
                rollback_of_plan_id,
                source_plan_id,
                message
            FROM surepython_plans
            WHERE plan_uuid = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (plan_uuid,),
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        return None
    return _plan_record_from_row(row)


def read_rollback_for_source_plan(db_path: Path, source_plan_id: int) -> PlanRecord | None:
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
                plan_uuid,
                client_plan_id,
                name,
                description,
                plan_schema_version,
                plan_path,
                metadata_json,
                preview_hash,
                status,
                step_count,
                file_count,
                tests_requested,
                tests_passed,
                started_at,
                completed_at,
                error_code,
                rollback_of_plan_id,
                source_plan_id,
                message
            FROM surepython_plans
            WHERE rollback_of_plan_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (source_plan_id,),
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        return None
    return _plan_record_from_row(row)


def read_plan_steps(db_path: Path, plan_id: int) -> list[PlanStepRecord]:
    if not db_path.exists():
        raise FileNotFoundError(f"Database does not exist: {db_path}")

    connection = sqlite3.connect(str(db_path))
    try:
        ensure_schema(connection)
        rows = connection.execute(
            """
            SELECT
                id,
                plan_id,
                step_index,
                step_id,
                operation,
                file,
                arguments_json,
                status,
                result_json,
                error_code,
                before_sha256,
                after_sha256
            FROM surepython_plan_steps
            WHERE plan_id = ?
            ORDER BY step_index ASC, id ASC
            """,
            (plan_id,),
        ).fetchall()
    finally:
        connection.close()

    return [_plan_step_record_from_row(row) for row in rows]


def read_plan_files(db_path: Path, plan_id: int) -> list[PlanFileRecord]:
    if not db_path.exists():
        raise FileNotFoundError(f"Database does not exist: {db_path}")

    connection = sqlite3.connect(str(db_path))
    try:
        ensure_schema(connection)
        rows = connection.execute(
            """
            SELECT
                id,
                plan_id,
                file,
                before_sha256,
                after_sha256,
                before_bytes,
                after_bytes,
                restored
            FROM surepython_plan_files
            WHERE plan_id = ?
            ORDER BY id ASC
            """,
            (plan_id,),
        ).fetchall()
    finally:
        connection.close()

    return [_plan_file_record_from_row(row) for row in rows]


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
                expected_import_statement,
                removed_import_statement,
                removed_import_binding,
                import_match_count,
                decorator_expression,
                decorator_position,
                decorator_target_kind,
                expected_decorator_expression,
                expected_decorator_position,
                removed_decorator_expression,
                removed_decorator_position,
                parameter,
                expected_return_annotation,
                return_annotation,
                before_sha256,
                after_sha256,
                git_diff,
                pytest_command,
                pytest_exit_code,
                pytest_status,
                status,
                message,
                source_operation_id,
                target_kind,
                parameter_kind,
                expected_parameter_annotation,
                parameter_annotation,
                expected_docstring_text,
                removed_docstring_text,
                removed_docstring_source,
                docstring_target_kind,
                docstring_replacement_statement,
                before_source_b64
            FROM surepython_operations
            WHERE id = ?
            """,
            (operation_id,),
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        raise FileNotFoundError(f"Operation not found: {operation_id}")

    return _operation_record_from_row(row)


def insert_plan_bundle(
    db_path: Path,
    plan_record: PlanRecord,
    step_records: list[PlanStepRecord],
    file_records: list[PlanFileRecord],
) -> int:
    connection = sqlite3.connect(str(db_path))
    try:
        ensure_schema(connection)
        cursor = connection.execute(
            """
            INSERT INTO surepython_plans (
                created_at,
                project_path,
                plan_uuid,
                client_plan_id,
                name,
                description,
                plan_schema_version,
                plan_path,
                metadata_json,
                preview_hash,
                status,
                step_count,
                file_count,
                tests_requested,
                tests_passed,
                started_at,
                completed_at,
                error_code,
                rollback_of_plan_id,
                source_plan_id,
                message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan_record.created_at,
                plan_record.project_path,
                plan_record.plan_uuid,
                plan_record.client_plan_id,
                plan_record.name,
                plan_record.description,
                plan_record.plan_schema_version,
                plan_record.plan_path,
                plan_record.metadata_json,
                plan_record.preview_hash,
                plan_record.status,
                plan_record.step_count,
                plan_record.file_count,
                int(plan_record.tests_requested),
                None if plan_record.tests_passed is None else int(plan_record.tests_passed),
                plan_record.started_at,
                plan_record.completed_at,
                plan_record.error_code,
                plan_record.rollback_of_plan_id,
                plan_record.source_plan_id,
                plan_record.message,
            ),
        )
        plan_id = int(cursor.lastrowid)

        for step in step_records:
            connection.execute(
                """
                INSERT INTO surepython_plan_steps (
                    plan_id,
                    step_index,
                    step_id,
                    operation,
                    file,
                    arguments_json,
                    status,
                    result_json,
                    error_code,
                    before_sha256,
                    after_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    step.step_index,
                    step.step_id,
                    step.operation,
                    step.file,
                    step.arguments_json,
                    step.status,
                    step.result_json,
                    step.error_code,
                    step.before_sha256,
                    step.after_sha256,
                ),
            )

        for file_record in file_records:
            connection.execute(
                """
                INSERT INTO surepython_plan_files (
                    plan_id,
                    file,
                    before_sha256,
                    after_sha256,
                    before_bytes,
                    after_bytes,
                    restored
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    file_record.file,
                    file_record.before_sha256,
                    file_record.after_sha256,
                    file_record.before_bytes,
                    file_record.after_bytes,
                    int(file_record.restored),
                ),
            )

        connection.commit()
        return plan_id
    finally:
        connection.close()


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
                expected_import_statement,
                removed_import_statement,
                removed_import_binding,
                import_match_count,
                decorator_expression,
                decorator_position,
                decorator_target_kind,
                expected_decorator_expression,
                expected_decorator_position,
                removed_decorator_expression,
                removed_decorator_position,
                parameter,
                expected_return_annotation,
                return_annotation,
                before_sha256,
                after_sha256,
                git_diff,
                pytest_command,
                pytest_exit_code,
                pytest_status,
                status,
                message,
                source_operation_id,
                target_kind,
                parameter_kind,
                expected_parameter_annotation,
                parameter_annotation,
                expected_docstring_text,
                removed_docstring_text,
                removed_docstring_source,
                docstring_target_kind,
                docstring_replacement_statement,
                before_source_b64
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

    return _operation_record_from_row(row)
