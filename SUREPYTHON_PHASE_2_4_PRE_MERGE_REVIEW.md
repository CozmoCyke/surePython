# SurePython Phase 2.4 Pre-Merge Review

Date: 2026-06-14

## Status

Ready for transfer.

No code correction was necessary during this review.

## Reviewed Commit

- `452eb726e22992a9f7e7685e42bc1c136d0bf7a7`
- `Add safe explicit import operation`

## Repository State At Review Time

- branch: `feature/phase-2.4-add-import`
- `main`: `47c7aa5fec1e61bc393c5c92544969995e7816e4`
- `origin/main`: `47c7aa5fec1e61bc393c5c92544969995e7816e4`
- public tag: `v0.6.0-public-preview`
- tag target: `47c7aa5fec1e61bc393c5c92544969995e7816e4`
- worktree: clean
- tests: `133 passed`

## Delta Inspected

The commit delta is limited to:

- `add-import`
- capabilities metadata
- JSON protocol support
- SQLite additive logging
- rollback support
- tests
- documentation
- phase 2.4 reports

No unrelated refactor, general import rewrites, or automatic inference logic was introduced.

## Accepted Import Forms

The operation accepts only explicit top-level single-binding statements such as:

- `import json`
- `import numpy as np`
- `from pathlib import Path`
- `from typing import Any as TypingAny`

The review confirmed that the binding reported by SurePython matches the canonical binding:

- `import json` -> `json`
- `import numpy as np` -> `np`
- `from pathlib import Path` -> `Path`
- `from typing import Any as TypingAny` -> `TypingAny`

## Refusals Confirmed

The review confirmed refusals for:

- empty statement
- non-import statement
- invalid syntax
- multiple statements separated by `;`
- multi-binding import
- wildcard import
- relative import
- duplicate import
- binding conflict

The stable refusal codes observed in the implementation are:

- `IMPORT_STATEMENT_REQUIRED`
- `IMPORT_STATEMENT_INVALID`
- `IMPORT_MULTIPLE_BINDINGS_UNSUPPORTED`
- `IMPORT_WILDCARD_UNSUPPORTED`
- `IMPORT_RELATIVE_UNSUPPORTED`
- `IMPORT_ALREADY_EXISTS`
- `IMPORT_BINDING_CONFLICT`
- `IMPORT_PLACEMENT_UNSUPPORTED`

## Duplicate And Conflict Behavior

Confirmed behavior:

- re-adding the same explicit import is refused with `IMPORT_ALREADY_EXISTS`
- changing only the source of an existing binding is refused with `IMPORT_BINDING_CONFLICT`
- the code and capabilities both treat binding identity as the conflict boundary

This is consistent and explicit.

## Placement Rules

Reviewed placement behavior:

- empty file: import becomes the first statement
- module docstring: import is inserted after the docstring
- `from __future__ import ...`: normal imports are placed after the future-import block
- shebang and encoding cookie are preserved
- existing imports are not sorted, merged, or rewritten
- comments and blank lines around the import block are preserved
- late executable code is not used as a basis for global import rearrangement

The implementation remains conservative: it inserts only into the initial safe import block.

## Byte-Exact Preservation

The review confirmed byte-exact rollback behavior for:

- LF
- CRLF
- UTF-8 BOM
- final newline present
- final newline absent
- shebang
- encoding cookie
- comments

The rollback path validates restored bytes against the logged `before_sha256` before writing.

## SQLite Compatibility

The SQLite extension is additive and idempotent.

New nullable columns:

- `import_statement`
- `import_binding`

Compatibility notes:

- older Phase 1.x, 2.0, 2.1, 2.2, and 2.3 databases remain readable
- old records remain usable with `NULL` in the new columns
- rollback for previous operations remains available
- no destructive schema migration was introduced

## Rollback Review

Confirmed rollback coverage:

- `add-import` supports `rollback --last`
- `add-import` supports `rollback --id <operation_id>`
- `source_operation_id` is recorded for rollback rows
- double rollback is refused with `ROLLBACK_ALREADY_APPLIED`
- historical or incompatible rows remain refused

The explicit-ID path selected only the requested operation during the smoke test.

## JSON Protocol Review

Confirmed protocol properties:

- `protocol_schema_version = "1.0"`
- `capabilities_schema_version = "1.0"`
- JSON mode emits structured JSON only
- successful `add-import` results expose:
  - `statement`
  - `binding`
  - `operation_id`
  - `written`
  - `logged`
  - `rollback_available`
  - `diff`
- refusal responses return `result: null`
- refusal responses carry stable error codes

## Capabilities Review

The capabilities contract now lists exactly:

- `add-docstring`
- `add-return-type`
- `add-parameter-type`
- `add-import`
- `rollback`

The `add-import` declaration matches the runtime behavior:

- one module file
- one explicit statement
- one binding
- dry-run supported
- tests supported
- logging supported
- rollback supported

## Real Smoke Test

The required temporary smoke was executed successfully in a clean temporary Git repository.

Smoke 1:

- `add-import --statement "from pathlib import Path" --dry-run --format json`
- `add-import --statement "from pathlib import Path" --test --db ... --format json`
- `rollback --id <operation_id> --dry-run --format json`
- `rollback --id <operation_id> --format json`
- second rollback refusal

Smoke 1 results:

- `operation_id = 1`
- `bytes_equal = true`
- `rollback_operation_id` was distinct from the source operation
- second rollback refused with `ROLLBACK_ALREADY_APPLIED`

Smoke 2:

- `add-import` followed by `add-parameter-type`
- rollback of the parameter annotation only
- rollback of the import afterward

Smoke 2 results:

- `add-import operation_id = 1`
- `add-parameter-type operation_id = 2`
- parameter rollback left the import intact
- final import rollback restored the original bytes exactly

## Self-Hosting Review

The phase 2.4 product implementation itself was done by direct Codex edits, not by self-hosted SurePython edits.

The honest coverage metric for repository code changes in this phase is therefore:

- SurePython-assisted product edits: `0`
- direct Codex product edits: `5`

That is acceptable for this phase because the new operation was not yet available when the implementation work began.

The validation and smoke execution did use the SurePython CLI directly and successfully.

## Codex Direct vs SurePython

The comparison remains honest:

- direct Codex is shorter when the tool itself is being extended
- SurePython is stricter, more bounded, and more auditable when the operation already exists
- no artificial self-hosting claim is made here

## Findings

No blocking defect was found in the reviewed Phase 2.4 commit.

## Risks Remaining

Residual risks are limited to the normal product boundaries:

- users could still attempt unsupported import forms and receive refusals
- rollback still depends on recorded historical hashes
- new behavior should continue to be guarded by `capabilities --format json` and `--dry-run`

## Recommendation

Proceed with transfer to `main`.

No hardening commit is required before merge.
