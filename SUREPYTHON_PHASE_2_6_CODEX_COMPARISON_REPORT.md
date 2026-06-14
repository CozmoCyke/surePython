# SurePython Phase 2.6 Codex Comparison Report

## Scope

This phase compared the direct Codex path with the intended SurePython-assisted path for a change that adds a new operation.

## Honest Baseline

Because `remove-return-type` did not exist at the start of the phase, the new plumbing could not be created through SurePython itself. The direct Codex path was therefore the only viable way to bootstrap the feature.

## Direct Codex Path

What happened:

- inspect the current codebase
- add the new command, codemod, rollback branch, SQLite fields, protocol codes, capabilities, and docs
- add tests for comparison, JSON, logging, and rollback
- validate with pytest

Strengths:

- fastest path for bootstrap work
- flexible enough to add new plumbing

Tradeoffs:

- no machine-readable proof trail for the write itself
- no automatic operation id for the bootstrap edits
- no automatic byte-exact preview for the code that creates the new capability

## Intended SurePython Path

Once the command exists, the intended future path for real user edits is:

```text
capabilities --format json
-> scan --format json
-> remove-return-type --dry-run --format json
-> remove-return-type --test --db <path>
-> rollback --id <operation_id>
```

Strengths after bootstrap:

- explicit target verification
- preview before writing
- structured JSON
- SQLite audit trail
- rollback by operation id
- byte-exact restoration

## Comparison Result

This phase is not a fair apples-to-apples benchmark for write-side self-hosting, because SurePython had to be extended before it could be used.

The honest conclusion is:

- the bootstrap plumbing was done directly
- the resulting capability is now suitable for future assisted edits
- SurePython becomes the preferred path only after the command exists in the capability registry

## Recommendation

Use SurePython for future supported return-annotation removals. Use direct Codex edits only for future bootstrap work that introduces a brand-new SurePython operation.