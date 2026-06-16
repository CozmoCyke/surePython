# SurePython Phase 3.0 Implementation Report

## Summary

Phase 3.0 introduces transactional multi-operation plans.
The implementation adds:

- a new `plan` command group with `preview`, `apply`, `rollback`, and `recover`
- additive SQLite storage for grouped plans
- a JSON plan schema contract
- deterministic preview hashes
- grouped rollback by `--last` or `--id`
- recovery for interrupted transactions
- capability reporting for the new command

## Public Contract

The public contract now includes:

- `python -m surepython capabilities --format json`
- `python -m surepython plan preview <plan.json> --format json`
- `python -m surepython plan apply <plan.json> --expect-preview-hash sha256:... --test --db <database.db> --format json`
- `python -m surepython plan rollback --last --db <database.db> --format json`
- `python -m surepython plan rollback --id <operation_id> --db <database.db> --format json`
- `python -m surepython plan recover --format json`

## Implementation Details

The implementation keeps the existing atomic operations unchanged and composes them into a transaction layer.

The transactional layer uses:

- the existing codemod functions for the actual file edits
- the existing Git guardrails
- the existing byte-exact rollback validation
- new grouped plan records in SQLite
- temporary recovery manifests outside the Git tree

## JSON And Capabilities

The JSON protocol stays on schema `1.0`.
The capabilities schema stays on schema `1.0`.

The new `plan` capability is machine-readable and declares:

- supported selectors: `preview`, `apply`, `rollback`, `recover`
- supported formats: `text`, `json`
- mutually exclusive selectors: yes
- additive error codes for plan validation, preview mismatch, plan rollback, and recovery

## SQLite Compatibility

The new tables are additive.
Existing phase 1.x and phase 2.x data remain valid.
No destructive migration was introduced.

## Validation

The implementation was validated with the full project test suite and the dedicated plan tests.

Observed results during development:

- full suite: `264 passed`
- plan tests: `5 passed`
- capabilities tests: `4 passed`

Additional validation already exercised:

- `python -m surepython capabilities --format json`
- `python -m surepython scan surepython --format json`
- `python -m surepython diff`
- `git diff --check`

## Operating Limits

This phase does not turn SurePython into a general workflow engine.
It only adds a grouped transaction wrapper around already supported micro-edits.

The following remain out of scope:

- arbitrary code generation
- arbitrary file rewriting
- silent rollback without a matching log record
- destructive SQLite changes
- automatic recovery without a manifest

## Implementation Conclusion

Phase 3.0 expands SurePython from single-operation safety into transactional safety.
It keeps the existing proof model intact while making multi-step work previewable, auditable, and recoverable.
