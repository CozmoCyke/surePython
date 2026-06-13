# SurePython Phase 2.4 Architecture Audit

Date: 2026-06-14

## Scope

Phase 2.4 adds `add-import`, a fourth controlled operation beside:

- `add-docstring`
- `add-return-type`
- `add-parameter-type`

The goal is to prove that SurePython can accept a new narrow edit without broadening into a general import rewriter.

## Existing Architecture

The current codebase already has four reusable layers:

1. `surepython/cli.py`
   - command routing
   - text and JSON protocol formatting
   - argument validation
2. `surepython/codemods.py`
   - LibCST-based transformations
   - byte-preserving file reconstruction
   - optional pytest execution
   - optional SQLite logging
3. `surepython/datasette_log.py`
   - SQLite schema management
   - record insertion and lookup
   - additive compatibility with older databases
4. `surepython/rollback.py`
   - byte-exact restoration
   - selection by `--last` or `--id`
   - refusal of `legacy/unverifiable` records

## Reusable Logic

The new operation reuses the same core guarantees as the other supported edits:

- clean Git worktree required
- file must stay inside the project root
- LibCST must parse the target module
- the supported change must be local and explicit
- the diff must be previewable
- pytest may be run after a real edit
- SQLite logging must stay auditable
- rollback must prove byte-exact restoration

## `add-import` Specific Behavior

The new operation is intentionally narrow:

- it accepts one explicit import statement
- it only supports one top-level import statement
- it only supports one binding
- it refuses wildcard, relative, or multi-binding imports
- it refuses conflicts with existing bindings
- it does not infer imports
- it does not rewrite or sort existing imports

Supported canonical examples:

- `import json`
- `import numpy as np`
- `from pathlib import Path`
- `from typing import Any as TypingAny`

## SQLite Impact

The schema extension is additive:

- `import_statement` is nullable
- `import_binding` is nullable
- older records remain readable
- older databases can be upgraded in place

This is compatible with the Phase 1.x, 2.0, and 2.1 log shape because the new columns are optional and only populated for `add-import`.

## Rollback Dispatch

Rollback now dispatches by operation type:

- `add-docstring`
- `add-return-type`
- `add-parameter-type`
- `add-import`

For `add-import`, rollback removes the exact top-level import statement that was logged. The operation remains byte-exact because the restored bytes are validated before writing.

## Protocol Compatibility

The JSON protocol remains rooted at schema version `1.0`.

Phase 2.4 does not change the envelope shape. It only adds:

- a new supported command
- a new capability entry
- new refusal codes for import-specific validation failures
- an import-specific target payload in the JSON result

## Risks And Mitigations

Main risks:

- accidentally broadening `add-import` into automatic import management
- accepting ambiguous import statements
- accepting import statements that cannot be restored exactly
- allowing rollback to treat older or incompatible histories as safe

Mitigations:

- exact import statement required
- single binding only
- strict refusal codes
- rollback only when the recorded bytes and hashes prove safety
- no compatibility shortcut that weakens hash checks

## Conclusion

Phase 2.4 stays within the SurePython design:

- one explicit action
- one explicit target
- one explicit safety envelope
- one exact rollback path

The architecture remains additive and conservative.
