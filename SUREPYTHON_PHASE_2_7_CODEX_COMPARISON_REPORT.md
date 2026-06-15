# SurePython Phase 2.7 Codex Comparison Report

## Goal

Compare direct Codex editing against SurePython-assisted editing for the new parameter-annotation removal workflow.

## Reality Of This Phase

The new operation did not exist at the start of the phase, so the implementation plumbing could not be done with SurePython yet.

That means the comparison is honest but asymmetric:

- direct Codex editing was required for the new operation plumbing
- SurePython was used for read-only discovery only
- once the capability exists, future edits can be compared directly against the new operation

## Comparison

### Direct Codex Editing

Strengths:

- can introduce the new operation itself
- can update protocol, rollback, logging, tests, and docs together

Tradeoffs:

- no operation_id trail for the plumbing work
- no pre-existing capability registry entry for the new operation
- no dry-run preview for the new operation while it is being built

### SurePython-Assisted Editing

For this phase, SurePython-assisted writes were not available for the new operation itself.

What SurePython did provide:

- capabilities discovery
- symbol scanning
- contract validation before edits

Benefits that will apply once the operation exists:

- narrow targeting
- preview before write
- exact compare-and-remove contract
- JSON protocol envelope
- SQLite logging
- rollback by operation id

## Conclusion

Phase 2.7 is a bootstrap phase, so direct edits were the correct and necessary fallback.

The comparison is therefore:

- direct editing: required for new plumbing
- SurePython-assisted writing: not yet applicable for the new operation

That is still valuable, because it preserves the rule that SurePython is used whenever the current capability set already covers the change.
