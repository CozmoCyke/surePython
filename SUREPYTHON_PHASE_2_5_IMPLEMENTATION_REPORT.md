# SurePython Phase 2.5 Implementation Report

## Result

Phase 2.5 adds `add-decorator` successfully and keeps the existing operations intact.

## Supported Operation

Command:

```powershell
python -m surepython add-decorator <file.py> --symbol <symbol> --decorator "<expression>" --position outermost|innermost
```

Supported targets:

- function
- async function
- method
- async method
- class

Supported behavior:

- exact decorator insertion
- `outermost` and `innermost` placement
- duplicate decorator refusal
- conflict refusal for binding helpers such as `staticmethod`, `classmethod`, and `property`
- `--dry-run`
- `--test`
- `--db`
- `--format json`
- rollback by `--last` or `--id`

## JSON Contract

The command returns the phase 1.0 protocol envelope and exposes:

- `decorator`
- `position`
- `target.kind`
- `operation_id` for real writes
- `operation_id: null` for dry-runs

## SQLite

The log schema was extended additively with nullable decorator fields.
Old rows and old rollback records remain readable.

## Validation

Completed checks:

- `python -m pytest --basetemp .\.tmp\pytest_phase_2_5 -q`
- `python -m surepython capabilities --format json`
- `python -m surepython scan surepython --format json`
- `python -m surepython add-decorator ... --dry-run --format json`
- real add-decorator smoke with `--test --db`
- rollback smoke with `--id` and a second refusal of `ROLLBACK_ALREADY_APPLIED`

Final automated test count: `155`.

## Limits

This phase does not add any other new codemod. The operation remains intentionally narrow and explicit.
