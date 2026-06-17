# SurePython Phase 3.1 Pre-Merge Review

## Summary

- Branch: `feature/phase-3.1-transaction-hardening`
- HEAD: `6a21c3db20fa79b36b50322e78c806014e8a884c`
- `main`: `503120d4bc2ccbee90402a39ddf0f471b4c95be3`
- `origin/main`: `503120d4bc2ccbee90402a39ddf0f471b4c95be3`
- Public tag: `v0.14.0-public-preview`
- Tag target: `503120d4bc2ccbee90402a39ddf0f471b4c95be3`
- Final test count: `295 passed`
- Worktree status after review changes: modified, pending commit

## Delta Inspected

- `surepython/transaction_lock.py`
- `surepython/protocol.py`
- `surepython/capabilities.py`
- `surepython/cli.py`
- `surepython/plans.py`
- `surepython/datasette_log.py`
- `tests/test_phase_3_1_transaction_hardening.py`
- Documentation updated earlier for Phase 3.1:
  - `docs/README.md`
  - `docs/TUTORIAL_FR.md`
  - `docs/CODEX_INTEGRATION.md`
  - `docs/AGENTS_TEMPLATE.md`
  - `docs/PROTOCOL_JSON.md`
  - `docs/SELF_HOSTING.md`
  - `docs/WINDOWS_TROUBLESHOOTING.md`

## Findings

1. Transaction recovery did not reconcile against SQLite durability.
   - A crash after the plan had committed to SQLite could leave a transaction manifest behind.
   - Recovery only looked at manifests and preimages, so it could not tell whether the plan had already become durable in SQLite.

2. `plan recover` needed access to the plan database path.
   - The manifest did not preserve enough information to reconcile recovery against the database row that created the plan.

3. Atomic codemods did not block while recovery was pending.
   - `add-docstring`, `add-return-type`, `add-import`, `add-decorator`, and the corresponding removal commands could still proceed while a transaction recovery was required.

4. Recovery cleanup needed a clearer terminal cleanup path.
   - Complete manifests with leftover preimages were being treated as recoverable cleanup cases, but normal rollback paths had to remain unaffected.

## Corrections Applied

- Added `read_plan_by_uuid()` in `surepython/datasette_log.py`.
- Persisted `db_path` in transactional plan manifests for apply and rollback.
- Added recovery classification helpers in `surepython/plans.py`.
- Extended `recover_plan()` to:
  - reconcile durable SQLite commits,
  - distinguish clean completion from user modification,
  - refuse conflicting states with `PLAN_RECOVERY_CONFLICT`,
  - clean up leftover preimages safely.
- Kept `_ensure_no_recovery_required()` focused on incomplete recovery states only.
- Added CLI guards so atomic codemods refuse with `PLAN_RECOVERY_REQUIRED` while recovery is pending.
- Added regression coverage for:
  - durable SQLite recovery without rewriting files,
  - user-modified file conflict,
  - atomic mutation refusal while recovery is required.

## Behavior Verified

- OS lock contention is distinguished from interrupted transaction recovery.
- Recovery is idempotent.
- Recovery after durable SQLite commit no longer rewrites already-final bytes.
- User modifications are detected and refused instead of being overwritten.
- Manifest integrity checks still reject invalid state and checksum values.
- Byte-exact restoration remains covered by the existing rollback and plan tests.

## Public Error Codes Reviewed

- `PROJECT_MUTATION_LOCKED`
- `PLAN_RECOVERY_REQUIRED`
- `PLAN_STATE_INVALID`
- `PLAN_MANIFEST_INVALID`
- `PLAN_RECOVERY_CONFLICT`
- `HASH_MISMATCH`
- `LEGACY_UNVERIFIABLE`
- `UNKNOWN_SQLITE_OPERATION`

## Validation

- Full test suite: `295 passed`
- Phase 3.1 focused suite: `6 passed`
- `surepython capabilities --format json`: OK
- `surepython scan surepython --format json`: OK
- `surepython diff`: OK
- `git diff --check`: OK

## Residual Risks

- Recovery still depends on the manifest/db pair being present and readable.
- Terminal manifest cleanup remains filesystem-dependent and should continue to be tested on Windows and POSIX.
- The current hardening is intentionally narrow: it improves recovery correctness without broadening plan semantics.

## Recommendation

Phase 3.1 is ready for transfer after committing the hardening fixes and this review report.
