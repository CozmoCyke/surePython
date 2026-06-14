# SurePython Phase 2.5 Codex Comparison Report

## Comparison Goal

Compare a direct Codex edit with a SurePython-assisted workflow for the same kind of decorator insertion task.

## Direct Codex Path

What direct editing provided:

- immediate access to the new plumbing work
- freedom to create the operation itself
- no bootstrap dependency on a pre-existing capability

What direct editing did not provide by itself:

- machine-readable capability discovery
- dry-run proof in the product contract
- operation logging in SQLite
- rollback by operation id
- byte-exact restoration proof

## SurePython-Assisted Path

Once `add-decorator` existed, SurePython provided:

- `capabilities --format json`
- `scan --format json`
- `add-decorator --dry-run --format json`
- `add-decorator --test --db --format json`
- explicit `operation_id`
- rollback by `--id`
- byte-exact restoration
- refusal of the second rollback

## Honest Result

For the implementation work itself, the comparison is honest:

- SurePython-assisted Python code edits: `0`
- direct Codex Python code edits: `8`

That is not a failure. It simply reflects the bootstrap reality that a new operation cannot be used before it exists.

For the validation and proof stage, SurePython was fully used.

## Practical Value

SurePython adds value where the proof matters most:

- exact target selection
- preview before write
- explicit decorator position
- stable JSON contract
- test execution after the edit
- SQLite audit trail
- rollback by id
- byte-exact Windows restoration

## Recommendation

Keep using direct Codex edits for brand-new operation plumbing, then switch immediately to SurePython for the supported operation once the capability appears in the registry.
