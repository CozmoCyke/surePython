# SurePython Phase 2.0 Architecture Audit

## Purpose

Phase 2.0 must prove that SurePython can host more than one safe operation without becoming a general-purpose rewriting engine.

This audit was performed before changing the implementation.

## Current Architecture

The current CLI exposes:

- `scan`
- `add-docstring`
- `diff`
- `log`
- `rollback`

The core implementation is intentionally small:

- `surepython/cli.py` owns argument parsing and command output.
- `surepython/scanner.py` discovers Python functions, classes, and methods with qualified names.
- `surepython/codemods.py` implements the `add-docstring` operation and shared helper behavior.
- `surepython/git_tools.py` owns Git root, clean status, path containment, diff, and hashing helpers.
- `surepython/datasette_log.py` owns the SQLite schema, operation records, state-file replay, and inserts.
- `surepython/rollback.py` implements rollback for the logged `add-docstring` operation.

## Reusable Logic

The following logic can be reused for Phase 2.0:

- Git repository detection.
- Clean worktree enforcement.
- Authorized project-root containment.
- Symbol scanning and ambiguity refusal.
- Qualified `Class.method` targeting.
- SHA-256 before/after hashing.
- Preview diff generation.
- pytest execution.
- SQLite `OperationRecord` writing.
- State-file writing for manual `surepython log`.
- Byte-level rollback reconstruction helpers for LF, CRLF, BOM, and final newline preservation.

## Add-Docstring-Specific Logic

The following logic is specific to `add-docstring`:

- the `TODO_DOCSTRING` skeleton string
- LibCST insertion of a first body statement
- refusal when an existing docstring is present
- rollback by removing the skeleton docstring statement
- rollback compatibility query that only reads `operation = 'add-docstring'`

## Duplication Risks

Adding `add-return-type` by copying `add_docstring()` wholesale would duplicate:

- Git checks
- target resolution
- parse/refusal logging
- dry-run behavior
- test execution behavior
- SQLite record construction
- CLI printing patterns

Phase 2.0 should avoid a large abstraction framework, but it should introduce just enough shared helpers to keep the second operation honest.

## Minimal Operation Registry

Phase 2.0 should add a small declarative registry that describes the operations actually available.

Each operation should expose:

- CLI name
- description
- target types
- required arguments
- dry-run support
- test support
- logging support
- rollback support
- status/version

This registry should power:

```powershell
python -m surepython capabilities
python -m surepython capabilities --format json
```

The registry must not advertise future or unsupported behavior.

## SQLite Compatibility

The existing `surepython_operations` table already stores:

- operation name
- symbol
- hashes
- git diff
- pytest fields
- status
- message

No destructive schema migration is required for Phase 2.0.

The operation field can distinguish:

- `add-docstring`
- `add-return-type`
- `rollback`

Existing `add-docstring` records remain compatible.

Rollback lookup should generalize from "latest add-docstring operation" to "latest rollback-compatible SurePython operation" while preserving support for old `add-docstring` rows.

## Rollback Strategy

Rollback must know the operation type before choosing the inverse transformation.

For Phase 2.0:

- `add-docstring` rollback removes the skeleton docstring.
- `add-return-type` rollback removes the return annotation added by SurePython.
- both rollback paths must validate `after_sha256` before reconstruction.
- both rollback paths must select restored bytes only when SHA-256 equals `before_sha256`.
- `legacy/unverifiable` records remain refused without writing.

No rollback by date, range, Git blob, or approximation should be added.

## Add-Return-Type Scope

The new operation should:

- target exactly one function or method
- accept global function names and qualified `Class.method`
- receive the annotation explicitly
- validate annotation syntax before mutation
- refuse existing return annotations
- modify only the return annotation
- avoid import management
- preserve function body and formatting through LibCST
- support dry-run, pytest, SQLite logging, and rollback

## Recommended Implementation Shape

Use small additions rather than a major refactor:

- add `surepython/capabilities.py` for the operation registry
- add `add_return_type()` beside `add_docstring()` in `surepython/codemods.py`
- reuse `_resolve_target()`, `_preview_diff()`, `_write_state()`, and `run_pytest()`
- generalize `datasette_log` read helper to fetch the latest compatible operation across supported operation names
- generalize `rollback.py` by dispatching to operation-specific removers
- add CLI commands without changing existing command behavior

## Guardrails

Phase 2.0 must not:

- add another codemod beyond `add-return-type`
- infer types
- replace annotations
- add imports
- touch parameters
- weaken Git cleanliness checks
- weaken hash checks
- migrate SQLite destructively
- break existing `add-docstring` behavior
