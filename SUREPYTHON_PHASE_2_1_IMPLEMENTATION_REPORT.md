# SurePython Phase 2.1 Implementation Report

## Objective

Phase 2.1 adds an agent-safe structured operation protocol without expanding SurePython's modification power.

The implementation adds:

- a shared protocol module with stable schema and error codes
- JSON output for supported operational commands
- a richer capabilities JSON contract
- SQLite `operation_id` exposure for real writes
- agent-simulated integration tests

No new codemod was introduced.

## Implemented Protocol

### Operational JSON Envelope

Operational commands now emit a deterministic envelope when `--format json` is requested:

- `protocol_schema_version`
- `command`
- `ok`
- `status`
- `error`
- `result`
- `meta`

### Capabilities JSON

`surepython capabilities --format json` now returns:

- `protocol_schema_version`
- `capabilities_schema_version`
- `operations`

Each declared operation includes:

- `name`
- `description`
- `status`
- `targets`
- `required_arguments`
- `optional_arguments`
- `supports_dry_run`
- `supports_tests`
- `supports_logging`
- `supports_rollback`
- `supported_formats`
- `possible_error_codes`

## Error Codes And Exit Codes

Stable error codes are centralized in `surepython/protocol.py`.

Important codes used in this phase:

- `ANNOTATION_EXISTS`
- `ANNOTATION_INVALID`
- `FILE_NOT_FOUND`
- `FILE_OUTSIDE_PROJECT`
- `GIT_DIRTY`
- `GIT_NOT_REPOSITORY`
- `HASH_MISMATCH`
- `LEGACY_UNVERIFIABLE`
- `ROLLBACK_NOT_AVAILABLE`
- `TARGET_AMBIGUOUS`
- `TARGET_NOT_FOUND`
- `TARGET_UNSUPPORTED`
- `TESTS_FAILED`
- `UNKNOWN_SQLITE_OPERATION`

Exit codes are stable:

- `0` success
- `2` refusal or usage error
- `3` tests failed
- `4` security or hash mismatch
- `5` internal error

## Operation Identifiers

`datasette_log.insert_record()` now returns the SQLite row id.

Operational responses expose:

- `operation_id` for real writes
- `operation_id: null` for dry-runs and refusals
- `source_operation_id` and rollback `operation_id` for rollback responses

No schema migration was required; the existing autoincrement key was enough.

## Command Behavior

### `add-docstring`

- supports `--format json`
- supports dry-run JSON previews
- supports real writes with `--test` and optional `--db`
- refuses existing docstrings with structured error codes
- no longer logs dry-runs to SQLite

### `add-return-type`

- supports `--format json`
- supports dry-run JSON previews
- supports real writes with `--test` and optional `--db`
- refuses invalid, missing, ambiguous, or existing annotations with structured error codes
- no longer logs dry-runs to SQLite

### `rollback`

- supports `--format json`
- returns source operation metadata
- returns byte-exact validation status
- refuses unknown SQLite operation types explicitly
- preserves the `legacy/unverifiable` refusal path

### `capabilities`

- now advertises the supported operations with protocol and capabilities schema versions

## Tests

The phase adds coverage for:

- deterministic capabilities JSON
- structured JSON dry-runs for `add-docstring`
- structured JSON dry-runs for `add-return-type`
- JSON application with `--test` and `--db`
- JSON rollback preview
- JSON rollback success
- JSON refusal for unknown SQLite operation types
- agent-style end-to-end operation flow

Final validation result:

```text
68 passed
```

## Compatibility

Text output remains the default for the CLI.

The existing scan formats remain unchanged:

- text
- JSON
- CSV

The rollback byte-exact contract from phase 1.7 remains intact.

## Limits Remaining

Phase 2.1 still does not add:

- a third codemod
- automatic type inference
- import insertion for annotations
- multi-file edits
- rollback by range or date
- an HTTP or MCP server
- arbitrary workspace-wide rewriting

## Recommendation

Phase 2.1 is ready to merge once the documentation review is complete and the JSON protocol is treated as a stable public contract.
