# SurePython Phase 3.1 Implementation Report

## Result

Phase 3.1 adds transaction hardening for multi-operation plans. The code now serializes mutating work per project, validates manifest state more strictly, and injects explicit fault checkpoints for crash-safety tests.

## Code changes

- Added `surepython/transaction_lock.py` to provide a project-scoped non-blocking lock with metadata.
- Wrapped mutating CLI commands in the project mutation lock.
- Extended protocol error codes with:
  - `PROJECT_MUTATION_LOCKED`
  - `PLAN_STATE_INVALID`
  - `PLAN_MANIFEST_INVALID`
  - `PLAN_RECOVERY_CONFLICT`
- Hardened plan manifest handling with schema and checksum validation.
- Added recovery conflict detection and legacy-manifest compatibility handling.
- Added fault-injection checkpoints for apply, rollback, and recovery paths.
- Added regression tests for lock contention, manifest integrity, and recovery idempotence.

## Behavior changes

- Concurrent mutation attempts now fail with a structured refusal instead of racing.
- Invalid manifest state is rejected before apply or recovery.
- Conflicting incomplete manifests now produce a dedicated recovery conflict error.
- Fault injection can simulate crashes at specific transactional checkpoints.

## Compatibility

- Public protocol schema remains `1.0`.
- Existing plan rollback behavior remains available.
- Legacy manifests are still accepted when they contain the minimal required fields.

## Validation

- Full test suite: `292 passed`
- No new tag was created in this phase.
- No push was performed in this phase.

## Self-hosting honesty

The Phase 3.1 hardening code itself was edited directly rather than through a supported SurePython mutation operation. That is the correct fallback here because the work expands the engine that powers SurePython, not one of the already-supported codemods.
