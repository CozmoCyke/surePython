# SurePython Phase 2.6 Implementation Report

## Result

Phase 2.6 adds `remove-return-type` as a safe compare-and-remove codemod.

## Command

```powershell
python -m surepython remove-return-type <file.py> --function <symbol> --expect-annotation "<annotation>" [--dry-run] [--test] [--db <path>] [--format json]
```

## Behavior

The command:

- targets one function or method
- accepts qualified names such as `Class.method`
- compares the expected annotation against the actual return annotation before editing
- refuses when the return annotation is absent
- refuses when the actual annotation does not match the expected annotation
- removes only the return annotation when the comparison succeeds
- preserves the rest of the signature, body, decorators, comments, indentation, LF/CRLF, BOM, and final newline
- supports `--dry-run`
- supports `--test`
- supports `--db`
- supports `--format json`

## JSON Contract

The command uses the phase 1.0 protocol envelope and returns:

- `expected_annotation`
- `annotation` for the removed annotation source
- `operation_id` for real SQLite writes
- `operation_id: null` for dry-runs
- `tests` metadata when `--test` is used

Refusals are structured and use stable codes such as:

- `RETURN_ANNOTATION_REQUIRED`
- `RETURN_ANNOTATION_INVALID`
- `RETURN_ANNOTATION_NOT_FOUND`
- `RETURN_ANNOTATION_MISMATCH`

## SQLite

The log schema was extended additively with nullable columns:

- `expected_return_annotation`
- `return_annotation`

Older databases remain compatible.

## Rollback

Rollback now understands `remove-return-type` records and reinserts the stored return annotation source.

The explicit rollback contract still applies:

- `rollback --last`
- `rollback --id <operation_id>`
- byte-exact restoration
- refusal of double rollback
- refusal of `legacy/unverifiable` records

## Validation

Validation completed successfully:

- `python -m pytest tests/test_capabilities.py tests/test_remove_return_type.py -q` -> `19 passed`
- `python -m pytest --basetemp .\\.tmp\\pytest_phase_2_6 -q` -> `170 passed`
- `python -m surepython capabilities --format json`
- `python -m surepython scan surepython --format json`
- `python -m surepython diff`
- `git diff --check`

The validation commands that do not write files did not introduce any extra changes beyond the intended working tree edits.

## Limits

This phase does not add inference, import management, or multi-edit behavior. It remains a single safe transformation with explicit comparison.
