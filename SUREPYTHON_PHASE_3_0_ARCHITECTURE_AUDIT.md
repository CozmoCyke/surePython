# SurePython Phase 3.0 Architecture Audit

## Purpose

Phase 3.0 adds a transactional `plan` layer on top of the existing atomic SurePython operations.
The goal is not to invent a general workflow engine. The goal is to group already supported micro-edits into a previewable, testable, logged, and recoverable transaction.

## Existing Architecture Reused

The implementation reuses the established SurePython building blocks:

- `capabilities --format json` remains the machine-readable contract for agents
- `scan --format json` remains the symbol discovery layer
- atomic codemods still perform the actual file edits
- `--dry-run` still previews without writing
- `--test` still runs pytest after a real edit
- SQLite remains the audit trail
- rollback remains byte-exact and hash-guarded

## Transaction Model

The new `plan` command is split into four selectors:

- `preview`
- `apply`
- `rollback`
- `recover`

The plan file is a JSON object with:

- `plan_schema_version`
- optional `name`
- optional `description`
- optional `client_plan_id`
- optional `metadata`
- `steps`

Each step carries:

- `id`
- `operation`
- `file`
- `arguments`

The supported step operations are the already published atomic operations:

- `add-docstring`
- `remove-docstring`
- `add-return-type`
- `remove-return-type`
- `add-parameter-type`
- `remove-parameter-type`
- `add-import`
- `remove-import`
- `add-decorator`
- `remove-decorator`

## SQLite Design

The plan implementation uses additive SQLite tables rather than rewriting the existing log schema:

- `surepython_plans`
- `surepython_plan_steps`
- `surepython_plan_files`

This keeps phase 1.x and phase 2.x records readable and leaves the historical atomic operation rows untouched.

The plan tables store:

- grouped plan metadata
- ordered steps
- touched files
- before and after SHA-256 values
- the preview hash
- pytest status when requested
- rollback linkage through `source_plan_id` and `rollback_of_plan_id`

## Preview And Apply Contract

`plan preview` returns a deterministic `preview_hash` with the `sha256:` prefix.

`plan apply` refuses unless the caller supplies the exact preview hash produced by the matching preview.

This prevents stale or drifted plan application and makes the preview an explicit proof artifact.

## Rollback Contract

`plan rollback` is a grouped rollback, not an atomic codemod rollback.

It supports exactly one selector at a time:

- `--last`
- `--id <plan_operation_id>`

The rollback path refuses when:

- the plan already has a rollback record
- the selected plan belongs to another project
- the current bytes do not match the logged state
- the plan requires recovery

## Recovery Contract

Interrupted transactions write manifests and preimages outside the repository tree.
`plan recover` restores the interrupted bytes from that workspace without relying on Git as a substitute source of truth.

## Compatibility Notes

Compatibility was preserved by design:

- no destructive SQLite migration was introduced
- the JSON protocol envelope remains `1.0`
- the capabilities schema remains `1.0`
- atomic operations still work as before
- rollback by `--last` and `--id` remain explicit and mutually exclusive

## Risks Considered

- the plan engine adds orchestration complexity, so the preview hash check is mandatory
- recovery state lives outside the Git tree, so it must be documented clearly for Windows users
- `plan` is an experimental capability, so Codex should still inspect `capabilities --format json` before using it

## Audit Conclusion

The chosen architecture is minimal, additive, and aligned with the existing SurePython safety model.
It extends the system from single-operation proof to grouped-operation proof without weakening the underlying guardrails.
