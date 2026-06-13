# SurePython Phase 2.2 Codex Comparison Report

Repository: `C:\dev\datasette-lab\surePython`

Branch: `feature/phase-2.2-rollback-by-id-self-hosting`

## Comparison Goal

Compare two ways of completing the same controlled micro-change in a temporary repo:

- direct Codex edit
- Codex + SurePython

Target task:

- add one explicit return annotation to `SampleClass.sample_method`

The comparison focuses on proof quality, previewing, diff clarity, test execution, logging, and reversibility. It does not reduce the decision to speed.

## Direct Codex Path

Observed in the temporary direct repo:

- files modified: `1`
- diff stat: `sample.py | 2 +-`
- diff name-status: `M sample.py`
- pytest exit code: `0`
- rollback method: `git restore`
- rollback restored bytes exactly: `true`

Strengths:

- shortest path
- no tool overhead

Limitations:

- no structured preview envelope
- no operation id
- no SQLite audit trail
- rollback is Git-level, not operation-aware

## SurePython Path

Observed in the temporary SurePython repo:

Workflow:

```text
capabilities JSON
-> scan JSON
-> add-return-type dry-run JSON
-> add-return-type apply with --test --db
-> operation_id
-> commit
-> rollback --id <operation_id> dry-run JSON
-> rollback --id <operation_id> real JSON
-> double rollback refused
```

Observed metrics:

- capabilities exit code: `0`
- scan exit code: `0`
- dry-run exit code: `0`
- apply exit code: `0`
- tests exit code: `0`
- operation id: `1`
- rollback preview exit code: `0`
- rollback real exit code: `0`
- double rollback exit code: `2`
- double rollback error code: `ROLLBACK_ALREADY_APPLIED`
- bytes restored exactly: `true`
- Git status after commit: clean
- diff after rollback: empty

Structured proof produced:

- JSON preview with `selector.type = "operation_id"`
- JSON result with `source_operation_id = 1`
- JSON result with `rollback_operation_id = 2`
- SQLite rollback row recorded distinctly from the source row

Strengths:

- explicit preview before writing
- machine-readable JSON contract
- operation id recorded and re-used
- audit trail in SQLite
- byte-exact rollback proof
- duplicate rollback refusal

Limitations:

- more steps than direct editing
- requires a clean worktree for write operations

## Honest Conclusion

Direct Codex is shorter.

SurePython is safer when the goal is to prove a bounded transformation, keep a durable audit trail, and recover by operation id with byte-exact evidence.

In the comparison smoke, SurePython's added value was not speed. It was:

- bounded scope
- previewability
- operation ids
- rollback by id
- SQLite proof
- double-rollback refusal
