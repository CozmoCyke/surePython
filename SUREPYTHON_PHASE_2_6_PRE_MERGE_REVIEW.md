# SurePython Phase 2.6 Pre-Merge Review

## Summary

Phase 2.6 is ready for transfer.

I reviewed the `remove-return-type` implementation, the SQLite and rollback plumbing, the JSON protocol surface, the capabilities registry, and the phase-specific tests. I did not find a blocking defect that requires a correction commit.

## Repository State

- Branch: `feature/phase-2.6-remove-return-type`
- HEAD: `a3fe285e2787bb894cef8788fff24ead7e159600`
- `main` / `origin/main`: `cb4766f82a5688043258ab954aa28046d5902c88`
- Public tag: `v0.8.0-public-preview`
- Tag target: `cb4766f82a5688043258ab954aa28046d5902c88`
- Worktree: clean
- Tests: `170 passed`
- Pushes: none
- New tags: none

## Delta Inspected

The Phase 2.6 delta is limited to:

- `remove-return-type`
- compare-and-remove validation
- new return-annotation error codes
- capabilities registry updates
- JSON protocol updates
- additive SQLite schema changes
- rollback support
- tests
- documentation
- phase reports

Relevant code areas:

- `surepython/codemods.py:264, 1271, 1814`
- `surepython/rollback.py:411, 441, 505, 532, 573`
- `surepython/datasette_log.py:16, 66, 152, 294, 365`
- `surepython/cli.py:63, 107, 557, 862, 929`
- `surepython/capabilities.py:106`
- `surepython/protocol.py:29, 82`
- `tests/test_remove_return_type.py:69`

## Review Results

### 1. Exact targeting and compare-and-remove

`remove-return-type` resolves only function or method targets and compares the expected annotation before removal.

The implementation rejects:

- absent return annotations
- mismatched expected annotations
- invalid or missing expected annotation text
- non-function targets through the existing symbol resolution path

### 2. Preservation

The operation removes only the return annotation and leaves intact:

- decorators
- `async`
- parameters
- positional-only and keyword-only markers
- parameter annotations
- defaults
- docstrings
- function bodies
- indentation and comments

### 3. Rollback

Rollback support is wired for `remove-return-type` and remains byte-exact through the same rollback-by-id / rollback-last model used by the earlier operations.

The rollback path retains compatibility with historical records and continues to refuse:

- `GIT_DIRTY`
- `HASH_MISMATCH`
- `LEGACY_UNVERIFIABLE`
- `UNKNOWN_SQLITE_OPERATION`
- `PROJECT_MISMATCH`

### 4. SQLite and protocol

The new SQLite columns are additive and nullable:

- `expected_return_annotation`
- `return_annotation`

The JSON protocol still reports schema version `1.0`, and the new error codes are centralized in the protocol layer.

### 5. Capabilities

`remove-return-type` is declared in the capabilities registry with the correct targets, required arguments, and return-annotation error codes.

### 6. Tests

The new test coverage exercises:

- successful removal for functions and methods
- async functions
- multiline signatures
- classmethod preservation
- JSON preview and application
- mismatch refusal
- missing annotation refusal
- invalid expected annotation refusal
- rollback by id
- rollback last
- double rollback refusal

## Findings

No blocking findings.

## Recommendation

Ready for transfer to `main`.

Do not push from this review branch. Do not create or move tags.
