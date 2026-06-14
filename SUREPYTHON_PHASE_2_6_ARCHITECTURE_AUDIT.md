# SurePython Phase 2.6 Architecture Audit

## Scope

Phase 2.6 adds a new safe codemod: `remove-return-type`.

Goal: remove exactly one explicit return annotation from one targeted function or method after verifying that the actual annotation matches the expected annotation.

## Existing Architecture

The codebase already has a shared pattern for supported micro-edits:

- resolve a unique symbol through the scanner
- confirm the file is inside the authorized project root
- require a clean Git worktree
- parse with AST and LibCST
- produce a preview diff
- optionally run pytest
- write an SQLite record only for real writes
- reconstruct rollback bytes from logged state

`add-return-type` is the closest existing model. It already proves that:

- qualified targets work for functions and methods
- return annotations can be inserted without touching unrelated syntax
- byte preservation across LF, CRLF, final newline, and UTF-8 BOM is possible
- rollback can remove the annotation and restore the original file bytes

## Minimal Delta Required

A new removal operation needs only a small extension of the current system:

- a new CLI command: `remove-return-type`
- a new codemod path in `surepython/codemods.py`
- a new rollback branch that reinserts the removed return annotation
- new protocol error codes for absent or mismatched return annotations
- additive SQLite columns to store the expected annotation and the removed annotation source
- capability registry updates
- documentation updates
- tests for compare-and-remove, rollback, JSON, and preservation cases

## SQLite Compatibility

The schema extension is additive and nullable:

- `expected_return_annotation TEXT`
- `return_annotation TEXT`

This keeps older databases readable and lets newer records carry enough information for exact rollback.

No destructive migration is required.

## Rollback Design

Rollback for `remove-return-type` is the inverse of the new operation:

- read the stored removed annotation source
- verify the current file hash matches the logged `after_sha256`
- reinsert the annotation only for the targeted symbol
- reconstruct the exact bytes before writing
- refuse on `legacy/unverifiable` or double rollback

The existing rollback contract stays intact:

- `--last` continues to work
- `--id <operation_id>` remains explicit and exclusive with `--last`
- `source_operation_id` remains the link between the rollback and the source change

## Protocol Impact

The JSON protocol stays at root schema `1.0`.

New stable error codes are needed:

- `RETURN_ANNOTATION_REQUIRED`
- `RETURN_ANNOTATION_INVALID`
- `RETURN_ANNOTATION_NOT_FOUND`
- `RETURN_ANNOTATION_MISMATCH`

The command should emit structured JSON only when `--format json` is requested, with no stdout pollution.

## Risks

Main risks identified during the audit:

- comparing annotations by semantics instead of structure would weaken the proof
- storing only the expected annotation would not be enough for exact rollback
- changing the schema non-additively would break old logs and older reports
- forgetting to teach rollback about the new operation would strand the new log records

## Recommendation

Implement `remove-return-type` as a narrow compare-and-remove codemod with additive SQLite columns and a dedicated rollback branch. Do not expand it into inference, import management, or multi-edit behavior.