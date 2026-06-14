# SurePython Phase 2.5 Architecture Audit

## Scope

Phase 2.5 adds `add-decorator`, a third style of safe micro-modification alongside docstrings, return annotations, parameter annotations, and explicit imports.

## Shared Architecture

The code path reuses the same safety spine as the earlier phases:

- Git cleanliness and project-root checks
- LibCST parsing and rewrite
- byte-preserving decode/encode helpers
- `--dry-run` previews
- optional pytest execution
- SQLite journaling
- rollback dispatch based on operation type
- structured JSON output through the protocol envelope

## Phase 2.5 Specific Logic

`add-decorator` needs a few extra constraints:

- exact target selection by symbol
- support for function, async function, method, async method, and class targets
- exact decorator expression validation
- explicit placement with `outermost` or `innermost`
- duplicate decorator detection
- conflict detection for decorator families such as `staticmethod`, `classmethod`, and `property`
- rollback support that removes the recorded decorator at the recorded position

## SQLite Impact

The schema extension is additive and nullable:

- `decorator_expression`
- `decorator_position`
- `decorator_target_kind`

Older rows remain valid because the new columns default to `NULL`.

## Compatibility Notes

- `rollback --last` stays available.
- `rollback --id <operation_id>` now works for decorator operations as well.
- Existing Phase 1.x, 2.0, 2.1, 2.2, 2.3, and 2.4 rows remain readable.
- `legacy/unverifiable` records are still refused without writing.

## Risks Considered

- Ambiguous symbol matching if a short name maps to more than one target.
- Decorator collisions when a method-binding helper already exists.
- Byte drift on Windows if BOM or newline handling changes.
- Rollback false positives if the recorded decorator text is not canonicalized.

## Outcome

The architecture remained narrow and additive. Phase 2.5 extends the proven pattern instead of introducing a new execution model.
