# SurePython Phase 2.4 Codex Comparison Report

Date: 2026-06-14

## Goal

Compare the shape of a narrow import-edit task when performed directly by Codex versus when performed through SurePython.

This phase focused on the product boundary, not on maximizing self-hosted editing.

## Direct Codex Path

Direct editing is the shortest path when:

- the change is still being designed
- the new operation does not yet exist
- the supporting schema and protocol are still changing

Direct editing was used for the Phase 2.4 implementation itself.

Observed properties:

- fast to express
- flexible during design
- no machine-readable operation proof
- no built-in rollback proof at the moment of edit
- no automatic audit trail unless added separately

## SurePython Path

SurePython is the better path when the operation already exists and is supported.

The expected flow is:

```text
capabilities -> scan -> dry-run -> apply -> pytest -> SQLite log -> rollback
```

Observed properties:

- explicit capability discovery
- exact target selection
- dry-run preview before writing
- test execution after a real edit
- structured JSON responses
- audit trail in SQLite
- byte-exact rollback for compatible records

## Honest Result For Phase 2.4

Phase 2.4 did not use SurePython as the editing mechanism for the repository code itself.

So the honest comparison is:

- Codex direct: 5 implementation changes in the repo
- SurePython-assisted self-hosting edits: 0

That is not a failure of the product. It is simply the actual method used for this phase.

## What SurePython Still Proved

Even without self-hosted edits, SurePython proved that:

- `add-import` is discoverable via `capabilities --format json`
- `add-import` is previewable via `--dry-run`
- `add-import` can log and test via `--test --db`
- `add-import` can roll back by logged operation
- the JSON protocol stays stable

## What Would Improve The Comparison Next

For a future phase, a better comparison would require:

- at least one repository change done through SurePython
- at least one matching direct-edit baseline
- identical task scope for both paths
- recorded time, diff, tests, and rollback evidence

## Conclusion

Phase 2.4 is productively additive, but it is not a self-hosting showcase.

The comparison is honest:

- direct Codex was used for the implementation work
- SurePython was used for validation of the new operation
- no inflated self-hosting claim is made
