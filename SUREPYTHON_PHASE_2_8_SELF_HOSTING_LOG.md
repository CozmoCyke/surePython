# SurePython Phase 2.8 Self-Hosting Log

## Purpose

This log records where SurePython was used to assist its own development and
where the work was done directly.

## Phase 2.8 Changes

| Change | Support by SurePython? | Method used | operation_id | Result | Fallback |
| --- | --- | --- | --- | --- | --- |
| Add `remove-decorator` codemod | Partial | Direct Codex edit with existing safe-operation patterns reused | n/a | Implemented | The operation itself did not yet exist, so it could not be used to create itself |
| Add rollback support for `remove-decorator` | Partial | Direct Codex edit | n/a | Implemented | Rollback dispatch required extension before the new operation could be dogfooded |
| Add SQLite fields for decorator removal | Partial | Direct Codex edit | n/a | Implemented | Schema needed to be extended before logging could capture the new metadata |
| Update capabilities registry and docs | No | Direct Codex edit | n/a | Implemented | Documentation and registry changes were not suitable for self-hosting |

## Coverage Summary

- Tracked self-hosting entries in this log: 4
- Entries completed with SurePython: 0
- Entries completed directly: 4
- Real self-hosting coverage for the tracked entries: 0%

## Notes

- No fallback was treated as a success case.
- No fake self-hosting claim was made.
- The new codemod is now available for future dogfooding once the codebase
  itself supports editing it through the supported operations.
