# SurePython Self-Hosting

SurePython Phase 2.2 uses SurePython as a safety layer when the requested change already matches a supported operation.

Phase 2.3 extends the product with `add-parameter-type`. Phase 2.4 extends it again with `add-import`. Phase 2.5 extends it with `add-decorator`. Phase 2.6 adds `remove-return-type`. Phase 2.7 adds `remove-parameter-type`. Phase 2.8 adds `remove-decorator`. Phase 2.9 adds `remove-import`. Phase 2.10 adds `remove-docstring`. Phase 3.0 adds transactional `plan` support. The implementation work that introduces a brand-new operation still requires direct Codex edits for the new plumbing, but once the capability exists, future parameter-annotation, import, decorator, return-annotation, exact import-removal, docstring-removal, or grouped transactional-plan changes should use it.

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
- remove an explicit return annotation from a function or method after verifying the expected annotation
- add an explicit annotation to a specific parameter on a function or method
- remove an explicit annotation from a specific parameter on a function or method after verifying the expected annotation
- add one explicit top-level import statement with a single binding to a module file
- remove one explicit top-level import statement from a module file after verifying the expected statement
- add one explicit decorator expression to a function, method, or class
- remove one explicit decorator expression from a function, method, or class after verifying the expected expression and position
- remove one exact docstring from a module, class, function, or method after verifying the expected logical text

Use the explicit rollback path when the operation has already been logged and must be reversed safely.

## When Codex Edits Directly

Codex may edit directly when the intended change is outside the current SurePython capability set, including:

- rollback selection by new selector types not yet supported
- building the initial `add-decorator` plumbing before that capability exists
- building the initial `remove-decorator` plumbing before that capability exists
- building the initial `remove-return-type` plumbing before that capability exists
- building the initial `remove-parameter-type` plumbing before that capability exists
- documentation and policy files
- comparison reports and implementation reports
- non-micro architectural changes
- the code that introduces a brand-new SurePython operation before that operation exists
- the code that introduces a brand-new transactional capability before that capability exists

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
- the new `add-decorator` operation had to be built before it could be used
- direct edits were therefore the correct fallback for the plumbing itself
- the new `remove-decorator` operation had to be built before it could be used
- direct edits were therefore the correct fallback for the plumbing itself
- the new `remove-import` operation had to be built before it could be used
- direct edits were therefore the correct fallback for the plumbing itself
- the new `remove-return-type` operation had to be built before it could be used
- direct edits were therefore the correct fallback for the plumbing itself
- the new `remove-docstring` operation had to be built before it could be used
- direct edits were therefore the correct fallback for the plumbing itself
- the new transactional `plan` capability had to be built before it could be used
- direct edits were therefore the correct fallback for the plan plumbing itself
- once the relevant capability is available, future parameter removals, docstring removals, and grouped transactional changes should prefer SurePython

## Phase 3.1 Note

Phase 3.1 hardens the transaction runtime rather than adding a new public edit kind.

- the project mutation lock is part of the execution contract
- manifest checksums and state validation are required for transactional workspaces
- recovery is now expected to be idempotent and conservative
- fault injection checkpoints exist for test-only crash recovery smokes

This phase is still a direct-edit fallback for SurePython's own plumbing, but the resulting transactional commands are now the preferred path for supported plans and mutating operations.

Do not reduce the comparison to speed alone.

## Boundary

SurePython is a quarantine layer, not a general Python assistant. It is valuable precisely because it refuses when the proof is missing.
