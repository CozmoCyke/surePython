# SurePython Phase 3.2 Breaking Change Audit

## Summary

No blocking public breakage was required for this phase.

The phase is intentionally additive:

- new contract snapshots
- new JSON schemas
- a metadata table for SQLite
- validation glue
- documentation updates

## Reviewed Breakage Candidates

### CLI

- no public command was removed
- no public option was renamed
- no option became mandatory unexpectedly
- no new command was introduced

### JSON

- the protocol envelope remains `1.0`
- capabilities remain `1.0`
- the plan schema remains `1.0`
- no existing field changed type or meaning

### SQLite

- `surepython_schema_metadata` was added additively
- existing tables and columns remain readable
- historical databases remain compatible under additive migration rules

### Error Codes

- no public code was deleted
- no public code was renamed
- no code changed meaning

## Decision

Phase 3.2 is a freeze, not a rename or migration phase.

If a later change needs to break compatibility, it must bring:

1. a migration note
2. a test suite update
3. a versioned contract bump
4. a release note entry

