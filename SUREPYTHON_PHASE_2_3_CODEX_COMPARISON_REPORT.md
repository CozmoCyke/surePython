# SurePython Phase 2.3 Codex Comparison Report

## Goal

Compare direct Codex editing with SurePython-assisted editing for the new parameter-annotation workflow.

## Honest Result

For the code that introduces `add-parameter-type`, the comparison is asymmetric:

- direct Codex editing was required to create the new capability
- SurePython could be used read-only to inspect capabilities and scan symbols
- SurePython could not be used for the new write path until the new operation existed

The external smoke test then showed the future benefit of the new path:

- the operation can be previewed and applied in a clean repository
- the resulting edit is logged with an `operation_id`
- rollback by explicit `--id` restores the original bytes
- project-boundary refusals remain active

That asymmetry is itself an important product fact.

## Comparison Table

| Aspect | Direct Codex Edit | SurePython-Assisted Edit |
|---|---|---|
| Capability discovery | manual reading / code inspection | `capabilities --format json` |
| Symbol discovery | manual / code navigation | `scan --format json` |
| Preview before write | available only if manually staged | future `add-parameter-type --dry-run` |
| Diff clarity | depends on manual care | expected to be narrow and explicit |
| Tests | manual invocation | `--test` and pytest integration |
| Logging | manual DB handling | automatic SQLite logging with `--db` |
| Rollback | Git/manual restore | `rollback --id <operation_id>` |
| Byte-exact proof | manual inspection | explicit hash-checked rollback |

## What Changed In Practice

- Direct edits: all 10 Python files
- SurePython write-assisted edits: 0
- Read-only SurePython checks: 2
- External smoke validations of the new operation: 1

## Interpretation

SurePython's value in Phase 2.3 is not that it replaced direct implementation work. Its value is that it now exposes a third safe operation that future edits can use without widening the trust boundary.

## Comparison Verdict

Direct editing remains necessary for bootstrapping new SurePython features.

SurePython remains the better tool for future parameter-annotation changes once the operation is available, because it gives:

- narrower scope
- explicit preview
- JSON protocol
- automated tests
- SQLite logging
- explicit rollback

## Recommendation

Use direct Codex edits only to extend the execution layer itself.

Use SurePython for supported user-facing micro-edits as soon as the capability exists.
