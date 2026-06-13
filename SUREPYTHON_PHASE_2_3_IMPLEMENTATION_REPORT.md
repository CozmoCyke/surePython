# SurePython Phase 2.3 Implementation Report

## Summary

Phase 2.3 adds a third supported codemod:

- `add-parameter-type`

The operation inserts one explicit annotation on one named parameter in one targeted function or method.

## Public Behavior

New CLI shape:

```powershell
python -m surepython add-parameter-type <file> --function <qualified_name> --parameter <name> --annotation "<expr>"
```

Supported flags:

- `--dry-run`
- `--test`
- `--db`
- `--format json`

## Supported Parameter Kinds

Allowed:

- positional-only
- positional-or-keyword
- keyword-only

Refused:

- variadic positional (`*args`)
- variadic keyword (`**kwargs`)

## Protocol and Logging

The implementation extends the existing contracts without changing the root protocol version:

- `protocol_schema_version = "1.0"`
- `capabilities_schema_version = "1.0"`

The SQLite log schema now records the selected `parameter` for parameter-type operations.

Rollback dispatch now understands:

- `add-docstring`
- `add-return-type`
- `add-parameter-type`

## Validation

Validation already completed during implementation:

- `python -m pytest` passes
- the full suite currently passes `111` tests
- `surepython capabilities --format json` declares `add-parameter-type`
- `surepython scan surepython --format json` remains stable

External smoke validation in a temporary clean repository also passed:

- `add-parameter-type` with `--test --db` applied successfully
- rollback by explicit `--id` succeeded after a clean commit
- the restored file hash matched the original byte for byte
- the rollback preview refused correctly when run from the wrong project root

## File Set

Modified Python files:

- `surepython/capabilities.py`
- `surepython/cli.py`
- `surepython/codemods.py`
- `surepython/datasette_log.py`
- `surepython/protocol.py`
- `surepython/rollback.py`
- `tests/test_add_parameter_type.py`
- `tests/test_capabilities.py`
- `tests/test_protocol_json.py`
- `tests/test_rollback.py`

Updated documentation:

- `AGENTS.md`
- `README.md`
- `docs/AGENTS_TEMPLATE.md`
- `docs/CODEX_INTEGRATION.md`
- `docs/PROTOCOL_JSON.md`
- `docs/SELF_HOSTING.md`
- `docs/TUTORIAL_FR.md`
- `docs/WINDOWS_TROUBLESHOOTING.md`

## Remaining Limits

Phase 2.3 does not attempt to:

- infer parameter names
- infer parameter annotations
- add imports automatically
- generalize to arbitrary AST rewrites
- change the rollback selection model beyond the existing explicit selectors

The smoke test also confirmed that the existing project-boundary checks remain active.

## Recommendation

Merge Phase 2.3 only after the documentation, self-hosting log, and comparison report are reviewed together with the code and tests.
