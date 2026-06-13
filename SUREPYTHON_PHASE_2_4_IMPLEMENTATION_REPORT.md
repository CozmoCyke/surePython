# SurePython Phase 2.4 Implementation Report

Date: 2026-06-14

## Summary

Phase 2.4 adds `add-import`, a safe explicit import insertion command for a single module file.

The implementation keeps the existing SurePython contract intact:

- dry-run first
- real edit only when the module and statement are valid
- optional pytest after a real edit
- optional SQLite logging
- rollback by exact logged record
- byte-for-byte preservation of the module text

## Implemented Changes

### Core editing

- Added `add_import(...)` to `surepython/codemods.py`
- Added `AddImportResult`
- Added import parsing and insertion helpers
- Preserved original encoding, BOM, and newline style when writing bytes
- Reused the existing LibCST-based parse and validation flow

### CLI

- Added `python -m surepython add-import <file> --statement "<import>"`
- Added `--dry-run`
- Added `--test`
- Added `--test-command`
- Added `--db`
- Added JSON protocol support for the new command
- Added a text summary for the new command

### Protocol

- Added import-specific refusal codes
- Kept protocol schema version `1.0`
- Kept JSON output deterministic and quiet

### Rollback

- Extended rollback to support `add-import`
- Added byte-exact removal of the inserted import statement
- Preserved compatibility with `--last` and `--id`

### SQLite

- Added nullable `import_statement`
- Added nullable `import_binding`
- Kept the schema extension additive and idempotent

### Capabilities

- Added `add-import` to the machine-readable capabilities contract
- Marked its supported target as `module`
- Declared support for dry-run, tests, logging, and rollback

### Documentation

- Updated `README.md`
- Updated `docs/AGENTS_TEMPLATE.md`
- Updated `docs/CODEX_INTEGRATION.md`
- Updated `docs/PROTOCOL_JSON.md`
- Updated `docs/SELF_HOSTING.md`
- Updated `docs/TUTORIAL_FR.md`
- Updated `docs/WINDOWS_TROUBLESHOOTING.md`
- Updated `AGENTS.md`

## Validation

Automated validation passed:

- `python -m pytest --basetemp .\.tmp\pytest_phase_2_4 -q`
- result: `133 passed`

Targeted checks also passed before the full suite:

- `tests/test_add_import.py`
- `tests/test_capabilities.py`
- `tests/test_protocol_json.py`

Static syntax checks passed through `py_compile` on the edited Python files.

## Manual Smoke

A temporary shell-based smoke test for `add-import -> commit -> rollback --id -> second rollback refusal` was attempted, but the shell tool hit a usage limit and rejected the command before execution.

That limitation did not affect the automated test results, but it means the repository-level smoke was not completed in this turn.

## Result

Phase 2.4 is implemented locally and validated by the test suite.

The new operation remains intentionally narrow:

- one file
- one explicit import statement
- one binding
- exact rollback support

## Recommendation

Ready for local commit after final diff review.
