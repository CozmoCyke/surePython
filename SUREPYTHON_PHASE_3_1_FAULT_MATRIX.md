# SurePython Phase 3.1 Fault Matrix

## Intent

This matrix records the expected hardening outcomes for concurrency, manifest validation, and recovery.

| Scenario | Trigger | Expected result | Notes |
| --- | --- | --- | --- |
| Concurrent mutation attempt | Another process already holds the project lock | `PROJECT_MUTATION_LOCKED` | No file or SQLite change |
| Invalid manifest structure | Manifest state or shape is malformed | `PLAN_STATE_INVALID` or `PLAN_MANIFEST_INVALID` | Fails closed |
| Tampered checksum | Manifest checksum does not match payload | `PLAN_MANIFEST_INVALID` | No recovery guesswork |
| Multiple incomplete manifests | More than one recoverable manifest is present | `PLAN_RECOVERY_CONFLICT` | Refuses to choose arbitrarily |
| Apply crash at checkpoint | `SUREPYTHON_PLAN_FAULT_AT` set during apply | Faulted process or `PLAN_DATABASE_FAILED` | Used to prove recovery paths |
| Rollback crash at checkpoint | Fault injection during rollback | Faulted process or `PLAN_DATABASE_FAILED` | Recovery can resume safely |
| Recovery crash at checkpoint | Fault injection during recovery | Faulted process or `PLAN_DATABASE_FAILED` | No silent success |

## Checkpoints exercised

- `apply:manifest-written`
- `apply:file-written`
- `apply:files-written`
- `apply:tests-passed`
- `apply:db-committed`
- `apply:complete`
- `rollback:manifest-written`
- `rollback:file-restored`
- `rollback:files-restored`
- `rollback:db-committed`
- `rollback:complete`
- `recover:manifest-read`
- `recover:file-restored`
- `recover:files-restored`
- `recover:manifest-written`

## Expected safety properties

- Failures do not produce a false success log.
- Recovery remains deterministic after an interrupted transaction.
- Legacy manifests are still accepted when they are structurally valid enough to recover.
- The lock prevents two writers from mutating the same project at the same time.
