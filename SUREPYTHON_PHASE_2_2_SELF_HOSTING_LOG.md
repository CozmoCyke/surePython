# SurePython Phase 2.2 Self-Hosting Log

Repository: `C:\dev\datasette-lab\surePython`

Branch: `feature/phase-2.2-rollback-by-id-self-hosting`

## Policy

SurePython should be used to perform a Python code change when the intended change is already supported by the current capability set. When no supported operation matches, direct Codex editing is allowed and must be recorded as a fallback.

## SurePython Repository Changes

The Phase 2.2 SurePython repository changes were outside the current supported capability set because the work introduced a new rollback selector, SQLite schema migration, protocol extension, and supporting tests.

Result:

- supported SurePython-assisted modifications on the SurePython repo: `0`
- direct edits on the SurePython repo: `14` files changed in the current diff

Fallback reasons:

- `rollback --id` did not exist yet
- SQLite migration and protocol changes were outside the existing codemod lane
- docs and reports are not supported SurePython code operations

## Temporary Dogfood Smoke

To compare direct editing against SurePython assistance, a temporary comparison repo was created and exercised with the supported operation set.

Successful supported actions in the temp comparison repo:

- `capabilities --format json`
- `scan . --format json`
- `add-return-type ... --dry-run --format json`
- `add-return-type ... --test --db ... --format json`
- `rollback --id <operation_id> --dry-run --format json`
- `rollback --id <operation_id> --format json`

Observed results:

- one supported change was applied with SurePython in the temp comparison repo
- the rollback restored the file byte-for-byte
- a second rollback of the same `operation_id` was refused with `ROLLBACK_ALREADY_APPLIED`

## Totals

- SurePython repo Python changes made directly: `5` code files plus `3` test files
- SurePython repo Python changes made with SurePython: `0`
- temp comparison repo changes made with SurePython: `1` supported code edit plus explicit rollback proof
- temp comparison repo changes made directly: `1` direct manual edit for comparison

## Honest Fallback Note

Where the code introduced in Phase 2.2 was outside the current supported capability set, direct editing was the correct choice. The comparison smoke demonstrates where SurePython does add value today: bounded preview, operation ids, logging, byte-exact rollback, and refusal of duplicate rollback.
