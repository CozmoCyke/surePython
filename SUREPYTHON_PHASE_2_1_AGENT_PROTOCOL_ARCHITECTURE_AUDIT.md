# SurePython Phase 2.1 Architecture Audit

## Purpose

Phase 2.1 turns SurePython into a stable machine-readable protocol for agents without widening its power to modify code.

The audit focus is:

- structured JSON responses
- stable error codes
- stable CLI exit codes
- SQLite operation identifiers for real writes
- agent-simulated integration tests

## Current Architecture

The relevant modules are:

- `surepython/protocol.py`
- `surepython/cli.py`
- `surepython/capabilities.py`
- `surepython/codemods.py`
- `surepython/rollback.py`
- `surepython/datasette_log.py`
- `surepython/git_tools.py`

The architecture remains intentionally small:

- `cli.py` owns command parsing and response rendering.
- `protocol.py` owns schema versions, error codes, JSON envelopes, and deterministic serialization.
- `capabilities.py` owns the declarative supported-operation registry.
- `codemods.py` owns `add-docstring` and `add-return-type`.
- `rollback.py` owns rollback of the latest compatible logged operation.
- `datasette_log.py` owns the SQLite schema and insert/read helpers.

## Structured Outputs

The following commands can now emit structured JSON when `--format json` is requested:

- `capabilities`
- `add-docstring`
- `add-return-type`
- `rollback`

Text output remains the default.

The JSON envelope for operational commands is stable and deterministic:

- `protocol_schema_version`
- `command`
- `ok`
- `status`
- `error`
- `result`
- `meta`

`capabilities --format json` uses its own root payload and announces:

- `protocol_schema_version`
- `capabilities_schema_version`
- `operations`

## Stable Error Model

Phase 2.1 centralizes error codes so agents do not need to infer meaning from wording.

The supported codes include:

- `GIT_NOT_REPOSITORY`
- `GIT_DIRTY`
- `FILE_OUTSIDE_PROJECT`
- `FILE_NOT_FOUND`
- `PARSE_ERROR`
- `TARGET_NOT_FOUND`
- `TARGET_AMBIGUOUS`
- `TARGET_UNSUPPORTED`
- `DOCSTRING_EXISTS`
- `ANNOTATION_REQUIRED`
- `ANNOTATION_INVALID`
- `ANNOTATION_EXISTS`
- `UNSUPPORTED_OPERATION`
- `UNKNOWN_SQLITE_OPERATION`
- `HASH_MISMATCH`
- `LEGACY_UNVERIFIABLE`
- `TESTS_FAILED`
- `DATABASE_ERROR`
- `ROLLBACK_NOT_AVAILABLE`
- `INTERNAL_ERROR`

The codes map to stable process exit codes:

- `0` success
- `2` refusal or usage error
- `3` tests failed
- `4` security or hash mismatch
- `5` internal error

## SQLite Compatibility

The `surepython_operations` schema remains unchanged.

Phase 2.1 relies on the existing `id INTEGER PRIMARY KEY AUTOINCREMENT` column to expose an `operation_id` for real writes.

No destructive schema migration is required.

The logging contract is now:

- real operations with `--db` return an `operation_id`
- dry-runs return `operation_id: null`
- rollback returns both the source operation id and the rollback log id

## Compatibility Notes

The phase keeps the text CLI stable while adding JSON only when explicitly requested.

Compatible behaviors preserved:

- `scan` text output
- `scan --format json`
- `scan --format csv`
- `add-docstring` text output and dry-run behavior
- `add-return-type` text output and dry-run behavior
- `rollback` byte-exact reconstruction
- `legacy/unverifiable` refusals without writing

## Agent Simulation

The added tests validate an end-to-end agent-like workflow:

- query `capabilities --format json`
- choose `add-return-type`
- preview with JSON dry-run
- apply with `--test` and `--db`
- retrieve `operation_id`
- commit
- rollback dry-run with JSON
- rollback real with JSON
- verify byte-exact restoration and SQLite records

## Audit Conclusion

The architecture is ready for phase 2.1 because the protocol layer remains narrow, the JSON contract is explicit, and no new codemod was added.

