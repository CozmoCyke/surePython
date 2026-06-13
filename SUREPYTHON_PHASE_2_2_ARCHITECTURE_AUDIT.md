# SurePython Phase 2.2 Architecture Audit

Repository: `C:\dev\datasette-lab\surePython`

Branch: `feature/phase-2.2-rollback-by-id-self-hosting`

## Scope

Phase 2.2 extends the existing rollback contract without adding a third codemod. The new product behavior is explicit rollback selection by operation id:

```powershell
python -m surepython rollback --id 42 --db .\surepython.db
```

The pre-existing `--last` selector remains available.

## Current Architecture

The existing architecture already separates the main concerns:

- `surepython/codemods.py` handles supported edits and their logging
- `surepython/datasette_log.py` owns the SQLite schema and record I/O
- `surepython/rollback.py` reconstructs the prior bytes and validates hashes
- `surepython/protocol.py` defines the structured JSON envelope and error codes
- `surepython/cli.py` maps CLI flags to the protocol and exit codes
- `surepython/capabilities.py` exposes machine-readable operations

Phase 2.2 reuses that split instead of introducing a new service layer.

## Reading An Operation By ID

A rollback-by-id implementation needs a direct SQLite lookup by primary key.

Chosen approach:

- read one row with a parameterized `WHERE id = ?` query
- reject missing rows as `OPERATION_NOT_FOUND`
- reject `rollback` rows as `ROLLBACK_RECORD_NOT_ALLOWED`
- reject rows that belong to another project as `PROJECT_MISMATCH`
- reject rows whose current file hash no longer matches `after_sha256`

This keeps selection explicit and avoids reusing Git history as the source of truth.

## Compatibility With `--last`

`--last` remains the fallback selector for the latest compatible record.

Compatibility rules:

- `rollback --last --db ...` keeps the phase 2.1 behavior
- `rollback --id ... --db ...` selects one explicit source row
- both selectors are mutually exclusive
- the JSON protocol remains version `1.0`

## Detecting Double Rollback

The robust additive signal is `source_operation_id` stored on rollback rows.

Detection rule:

- once a source operation has a rollback row referencing it, a second rollback of the same source id is refused with `ROLLBACK_ALREADY_APPLIED`

This is stronger than inferring from file content alone because it survives byte-identical reversions and repeated manual edits.

## Historical / Older Bases

Old databases remain compatible because the schema migration is additive:

- add `source_operation_id INTEGER` if the column is missing
- backfill known rollback rows where a source can be inferred from the prior compatible record
- do not rewrite historical hashes
- do not delete rows

If a historical record still cannot be proven, it remains `legacy/unverifiable`.

## Migration Strategy

A destructive migration is not necessary.

The additive migration is:

1. create the table if needed
2. add `source_operation_id` if it is missing
3. backfill only where a prior compatible source record can be inferred

This is idempotent and safe to rerun.

## JSON Protocol

Phase 2.2 keeps `protocol_schema_version = "1.0"`.

The rollback result now includes:

- `selector.type`
- `selector.value`
- `source_operation_id`
- `rollback_operation_id`
- `bytes_equal`

The result remains stable and machine-readable for both text and JSON modes.

## Project Ownership

An explicit rollback by id must belong to the current project.

The CLI checks:

- a current Git root exists
- the selected record's `project_path` matches the current root
- the worktree is clean

This prevents cross-project misuse of a valid id.

## Conclusion

Phase 2.2 can be implemented safely with an additive SQLite migration and a stricter rollback selector.

No destructive migration is required.
No new codemod is required.
The compatibility boundary remains intact.
