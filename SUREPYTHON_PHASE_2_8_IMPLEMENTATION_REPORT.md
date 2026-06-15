# SurePython Phase 2.8 Implementation Report

## Summary

Phase 2.8 implements `remove-decorator`, which removes one explicit decorator
from one function, method, or class after verifying the expected decorator
expression and the requested position.

## Implemented Behavior

- Single-file, single-symbol operation.
- Supports `function`, `method`, and `class` targets.
- Validates `outermost` and `innermost` selection explicitly.
- Refuses missing decorators, wrong positions, ambiguous symbols, unsupported
  targets, and invalid decorator syntax.
- Preserves the remaining decorators, comments, surrounding structure, and
  byte-level layout.
- Supports `--dry-run`, `--test`, and `--db`.
- Emits structured JSON using the existing protocol root version `1.0`.
- Logs the removal in SQLite with decorator-specific fields.
- Supports rollback by re-inserting the recorded decorator expression at the
  recorded position.

## Files Changed

- `surepython/codemods.py`
- `surepython/cli.py`
- `surepython/datasette_log.py`
- `surepython/protocol.py`
- `surepython/capabilities.py`
- `surepython/rollback.py`
- `tests/test_remove_decorator.py`
- `tests/test_capabilities.py`
- `README.md`
- `AGENTS.md`
- `docs/AGENTS_TEMPLATE.md`
- `docs/CODEX_INTEGRATION.md`
- `docs/PROTOCOL_JSON.md`
- `docs/SELF_HOSTING.md`
- `docs/TUTORIAL_FR.md`
- `docs/WINDOWS_TROUBLESHOOTING.md`

## Validation

Completed validation:

- `python -m pytest --basetemp .\\.tmp\\pytest_phase_2_8 -q`
- `python -m surepython capabilities --format json`
- `python -m surepython scan surepython --format json`
- `git diff --check`

Result:

- `214 passed in 196.37s`

## Notes

- The capabilities registry now advertises `remove-decorator`.
- Rollback behavior is preserved for existing operations and extended for
  decorator removal.
- No push and no tag creation were performed during this phase.

## Conclusion

The new codemod is implemented and validated locally.
The repository is ready for a local commit of the Phase 2.8 work.
