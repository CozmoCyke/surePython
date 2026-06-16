# SurePython Phase 2.9 Architecture Audit

## Scope

Phase 2.9 adds a new safe explicit codemod:

- `remove-import`

This operation removes exactly one module-level import statement after verifying the expected statement text and structure.

## Current Architecture

The existing product architecture already separates:

- capability discovery via `surepython capabilities --format json`
- symbol discovery via `surepython scan`
- dry-run preview
- real edit with optional test execution
- SQLite logging
- explicit rollback by `--last` or `--id`
- stable JSON protocol envelopes

That structure is reusable for `remove-import` without changing the public protocol root versions.

## Reused Logic

The following logic is shared with earlier operations:

- project-root and Git cleanliness checks
- file existence and path boundary checks
- exact source parsing with LibCST
- dry-run vs real-write branching
- pytest execution on real writes
- SQLite logging
- rollback dispatch and refusal handling
- JSON/text output selection

## `remove-import` Specific Logic

`remove-import` needs its own compare-and-remove rules:

- exact module-level import statement matching
- structural statement comparison
- module-level scope only
- ambiguity detection
- nested-only match refusal
- wildcard, relative, and multi-binding refusal
- exact byte removal with preserved encoding and newline behavior

## Compatibility With Existing SQLite Logs

The schema change is additive:

- `expected_import_statement`
- `removed_import_statement`
- `removed_import_binding`
- `import_match_count`

Older rows remain readable because the new columns are nullable and the readers continue to return the full record shape.

## Rollback Compatibility

Rollback now needs to dispatch by source operation type:

- `add-import` remains restore-by-removing the inserted statement
- `remove-import` restores the exact removed bytes

Rollback by `--last` remains available, and `--id` is now the preferred explicit selector for Phase 2.2+ records.

## Risks And Mitigations

- Risk: BOM or newline drift during rollback
  - Mitigation: restore bytes in memory and validate SHA-256 before writing
- Risk: historical incoherent records
  - Mitigation: refuse with `LEGACY_UNVERIFIABLE`
- Risk: ambiguous import match
  - Mitigation: refuse with `IMPORT_AMBIGUOUS`
- Risk: nested-only match
  - Mitigation: refuse with `IMPORT_SCOPE_UNSUPPORTED`

## Conclusion

The architecture can absorb `remove-import` as another controlled micro-operation without broadening SurePython into a general refactoring engine.
