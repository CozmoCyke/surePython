# SurePython Self-Hosting

SurePython Phase 2.2 uses SurePython as a safety layer when the requested change already matches a supported operation.

Phase 2.3 extends the product with `add-parameter-type`. The implementation work that introduces a brand-new operation still requires direct Codex edits for the new plumbing, but once the capability exists, future parameter-annotation changes should use it.

## Principle

```text
Codex reasons and proposes broadly.
SurePython executes only the transformations it can prove.
```

## Required Loop

When a code change is within the current capability set:

1. Query `python -m surepython capabilities --format json`.
2. Use `python -m surepython scan` to locate the exact symbol.
3. Run the supported operation with `--dry-run --format json`.
4. Parse the JSON and inspect the result.
5. Apply with `--test --db`.
6. Record the returned `operation_id`.
7. If needed, roll back with `--id <operation_id>`.

## When SurePython Is Mandatory

Use SurePython when the intended edit is one of the supported micro-modifications:

- add a skeleton docstring to a function or method
- add an explicit return annotation to a function or method
- add an explicit annotation to a specific parameter on a function or method

Use the explicit rollback path when the operation has already been logged and must be reversed safely.

## When Codex Edits Directly

Codex may edit directly when the intended change is outside the current SurePython capability set, including:

- rollback selection by new selector types not yet supported
- documentation and policy files
- comparison reports and implementation reports
- non-micro architectural changes
- the code that introduces a brand-new SurePython operation before that operation exists

When a direct edit is necessary, record the fallback and the reason. Never claim that SurePython secured a change it did not actually perform.

## Comparison Lens

When comparing direct edits against SurePython-assisted edits, measure:

- targeted symbol precision
- preview quality
- diff size and readability
- pytest usage
- logging trail
- rollback evidence
- JSON contract clarity

## Phase 2.3 Note

Phase 2.3 is an honest self-hosting boundary case:

- read-only checks use SurePython capabilities and scanning
- the new `add-parameter-type` operation had to be built before it could be used
- direct edits were therefore the correct fallback for the plumbing itself
- once Phase 2.3 is merged, future parameter edits should prefer SurePython

Do not reduce the comparison to speed alone.

## Boundary

SurePython is a quarantine layer, not a general Python assistant. It is valuable precisely because it refuses when the proof is missing.
