# SurePython Phase 2.9 Implementation Report

## Summary

Phase 2.9 implements `remove-import`, a safe explicit module-level import removal operation.

The operation requires an exact `--expect-statement` match and refuses:

- missing statements
- invalid statements
- multi-binding imports
- wildcard imports
- relative imports
- nested-only matches
- ambiguous matches
- project and Git guardrail violations

## Implementation Notes

Code changes were applied in:

- `surepython/codemods.py`
- `surepython/rollback.py`
- `surepython/datasette_log.py`
- `surepython/cli.py`
- `surepython/protocol.py`
- `surepython/capabilities.py`
- `tests/test_remove_import.py`
- `tests/test_capabilities.py`

The implementation keeps the existing JSON protocol root version `1.0` and extends the operation registry to describe `remove-import`.

## SQLite

The log schema is extended additively with nullable columns for the import-removal contract:

- `expected_import_statement`
- `removed_import_statement`
- `removed_import_binding`
- `import_match_count`

No destructive migration was required.

## Rollback

Rollback now supports both:

- `rollback --last`
- `rollback --id <operation_id>`

For `remove-import`, rollback restores the exact removed bytes and validates the restored SHA-256 before writing.

## Validation

Validation completed successfully with:

- targeted tests: 31 passed
- full suite: 241 passed
- `surepython capabilities --format json`
- `surepython scan surepython --format json`
- `surepython diff`
- `git diff --check`

## Notable Rejections Verified

The implementation and tests verify refusal paths for:

- `IMPORT_NOT_FOUND`
- `IMPORT_AMBIGUOUS`
- `IMPORT_SCOPE_UNSUPPORTED`
- `GIT_DIRTY`
- `LEGACY_UNVERIFIABLE`

## Conclusion

`remove-import` is ready as a controlled, auditable micro-modification and preserves the existing SurePython safety model.
