# SurePython Phase 2.2 Implementation Report

Repository: `C:\dev\datasette-lab\surePython`

Branch: `feature/phase-2.2-rollback-by-id-self-hosting`

## Summary

Phase 2.2 adds an explicit rollback selector by operation id while preserving the existing `--last` selector and the phase 2.1 JSON protocol contract.

The implementation is additive:

- a new SQLite column, `source_operation_id`, tracks the source of rollback rows
- a new row lookup reads an operation by id with a parameterized query
- rollback by id refuses records from other projects, rollback rows, and already-rolled-back operations
- the JSON protocol now includes a `selector` object for rollback
- `capabilities --format json` now declares the rollback command alongside operations

No destructive migration was introduced.

## Files Changed

Code:

- `surepython/datasette_log.py`
- `surepython/rollback.py`
- `surepython/cli.py`
- `surepython/protocol.py`
- `surepython/capabilities.py`

Tests:

- `tests/test_capabilities.py`
- `tests/test_protocol_json.py`
- `tests/test_rollback.py`

Documentation:

- `README.md`
- `docs/PROTOCOL_JSON.md`
- `docs/CODEX_INTEGRATION.md`
- `docs/AGENTS_TEMPLATE.md`
- `docs/TUTORIAL_FR.md`
- `docs/WINDOWS_TROUBLESHOOTING.md`
- `docs/SELF_HOSTING.md`
- `SUREPYTHON_PHASE_2_2_ARCHITECTURE_AUDIT.md`

Policy:

- `AGENTS.md`

## Rollback By ID

Supported rollback selectors:

- `--last`
- `--id <operation_id>`

The selector is mutually exclusive. The CLI rejects missing selectors, selector conflicts, invalid ids, missing ids, project mismatches, unknown operations, rollback rows selected as source, already-applied rollbacks, hash mismatches, and `legacy/unverifiable` histories.

Rollback JSON now includes:

- `selector.type`
- `selector.value`
- `source_operation_id`
- `rollback_operation_id`
- `bytes_equal`

The legacy `byte_exact` field is still exposed for compatibility.

## SQLite Compatibility

The schema migration is additive and non-destructive:

1. create the table if missing
2. add `source_operation_id` if missing
3. backfill rollback rows where a prior compatible source can be inferred

Old records remain readable. Historical rows that still cannot be proven remain `legacy/unverifiable`.

## Protocol Compatibility

The protocol schema remains `1.0`.

The capabilities payload now declares:

- `operations`
- `commands`

The `rollback` command is described as a command, not as a codemod.

## Validation

Completed validation:

- `python -m pytest --basetemp .\\.tmp\\pytest_phase_2_2`
- `python -m surepython capabilities --format json`
- `python -m surepython scan surepython --format json`
- `python -m surepython diff`
- `git diff --check`

Results:

- 80 tests passed
- structured JSON commands remained parseable
- rollback by id smoke passed on a CRLF file
- double rollback by id was refused with `ROLLBACK_ALREADY_APPLIED`

## Residual Risks

- rollback-by-id is intentionally strict about project ownership
- `source_operation_id` backfill is heuristic for older rollback rows, but the migration remains additive and non-destructive
- the phase does not add any new codemod

## Recommendation

Ready for merge after final repository cleanliness and review of the comparison report.
