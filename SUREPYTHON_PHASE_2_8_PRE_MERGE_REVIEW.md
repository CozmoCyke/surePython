# SurePython Phase 2.8 Pre-Merge Review

## Head

- Branch: `feature/phase-2.8-remove-decorator`
- HEAD: `d1233f35725098eeb394be6bb834f84225234340`
- Commit subject: `Add safe explicit decorator removal`
- `main`: `5ecbe9a52a5462c29aa4cb8ef02b7ff011efff23`
- `origin/main`: `5ecbe9a52a5462c29aa4cb8ef02b7ff011efff23`
- Public tag: `v0.10.0-public-preview`
- Tagged commit: `5ecbe9a52a5462c29aa4cb8ef02b7ff011efff23`
- Worktree: clean

## Delta Inspected

The phase 2.8 delta is limited to:

- `remove-decorator`
- decorator expression validation
- explicit `outermost` / `innermost` position handling
- compare-and-remove logic
- public error codes
- protocol JSON wiring
- capabilities registry updates
- additive SQLite schema updates
- rollback support
- tests
- documentation
- phase reports

No unintended operation was introduced:

- no automatic removal of imports
- no runtime execution or resolution of decorators
- no multi-symbol modification
- no silent decorator reordering
- no composite operation beyond the requested removal

## Public Contract Review

Verified public error codes for the operation:

- `DECORATOR_REQUIRED`
- `DECORATOR_INVALID`
- `DECORATOR_POSITION_REQUIRED`
- `DECORATOR_POSITION_INVALID`
- `DECORATOR_NOT_FOUND`
- `DECORATOR_POSITION_MISMATCH`
- `DECORATOR_TARGET_UNSUPPORTED`

The codes are consistently declared in:

- `surepython/protocol.py`
- `surepython/capabilities.py`
- CLI refusal paths
- tests
- documentation

The JSON protocol remains rooted at `protocol_schema_version = "1.0"` and
`capabilities_schema_version = "1.0"`.

## Behavior Verified

- `outermost` removes the first requested decorator occurrence.
- `innermost` removes the last requested decorator occurrence.
- A unique decorator is removable from both positions.
- Absence is distinguished from position mismatch.
- Only one occurrence is removed.
- Remaining decorators preserve order.
- Function, method, async function, and class targets are supported.
- Comments, signatures, bodies, and class structure are preserved.
- Inline decorator comments are removed with the removed decorator.
- Multiline decorators are removed as a single block.
- Byte-exact rollback is preserved for LF, CRLF, BOM, and final-newline variants.

## SQLite Review

The schema extension is additive and nullable.

Relevant fields include:

- `expected_decorator_expression`
- `expected_decorator_position`
- `removed_decorator_expression`
- `removed_decorator_position`
- `decorator_target_kind`

Compatibility observations:

- older rows remain readable
- previous operations remain rollbackable
- rollback records continue to work with existing phases
- no destructive migration was introduced

## Rollback Review

Both selectors remain supported:

- `rollback --last`
- `rollback --id <operation_id>`

Rollback for `remove-decorator` restores the recorded decorator expression at
the recorded position, rather than guessing from the current file contents.

Verified properties:

- `source_operation_id` is tracked
- `rollback_operation_id` is distinct
- double rollback is refused
- historical legacy/unverifiable records remain refused

## Validation

Completed validation:

- `python -m pytest --basetemp .\\.tmp\\pytest_phase_2_8 -q`
- `python -m pytest tests\\test_remove_decorator.py tests\\test_capabilities.py -q`
- `python -m surepython capabilities --format json`
- `python -m surepython scan surepython --format json`
- `git diff --check`

Results:

- `214 passed in 196.37s`
- `24 passed in 62.05s`

## Self-Hosting Review

Tracked self-hosting entries in the phase 2.8 log:

- total tracked entries: 4
- entries completed with SurePython: 0
- entries completed directly: 4
- tracked-entry coverage: 0%

This is an honest bootstrap result. The new operation was implemented
directly, then validated and documented.

## Comparison Review

The comparison between direct Codex editing and Codex plus SurePython is
honest:

- direct Codex was necessary to bootstrap the new operation
- SurePython now provides the safer path for future decorator removal changes
- the tool adds preview, validation, logging, and byte-exact rollback
- the review does not claim a speed advantage without measurement

## Findings

No blocking defect was found in the reviewed delta.

## Recommendation

Ready for transfer to `main`.

The reviewed branch can be merged by fast-forward once the usual merge checks
are completed.
