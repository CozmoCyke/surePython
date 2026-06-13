# AGENTS.md Template For Projects Using SurePython

Copy this policy into a project's `AGENTS.md` when SurePython is used as the controlled execution layer for Python micro-modifications.

````markdown
# Agent Policy

## SurePython Boundary

Codex may reason, inspect, and propose broadly.

SurePython may execute only the transformations it explicitly supports.

Current supported operation:

- add one skeleton docstring to one Python function or method that has no existing docstring
- add one explicit return annotation to one Python function or method that has no existing return annotation

Current supported rollback:

- rollback the latest compatible SQLite-logged `add-docstring` or `add-return-type` operation

## Mandatory Workflow

Before a SurePython modification:

```powershell
python -m surepython capabilities --format json
python -m surepython scan <path> --format json
git status --short
```

For a docstring dry-run:

```powershell
python -m surepython add-docstring <file.py> --function <symbol> --dry-run
```

For a return annotation dry-run:

```powershell
python -m surepython add-return-type <file.py> --function <symbol> --annotation "<annotation>" --dry-run
```

For a real operation:

```powershell
python -m surepython add-docstring <file.py> --function <symbol> --test --db <database.db>
python -m surepython add-return-type <file.py> --function <symbol> --annotation "<annotation>" --test --db <database.db>
python -m surepython diff
git status --short
```

For rollback:

```powershell
python -m surepython rollback --last --db <database.db> --dry-run
python -m surepython rollback --last --db <database.db>
python -m surepython diff
git status --short
```

## Hard Rules

- Do not run a SurePython write operation when `git status --short` is not clean.
- Do not bypass `--dry-run` for supported operations.
- Do not modify more than one file per SurePython operation.
- Do not target more than one symbol per SurePython operation.
- Do not replace an existing docstring.
- Do not replace an existing return annotation.
- Do not infer return annotations.
- Do not add imports automatically.
- Do not broaden `Class.method` into a global function edit.
- Do not run rollback without `--db`.
- Do not run real rollback before rollback `--dry-run`.
- Do not edit SQLite hashes to make rollback succeed.
- Do not treat `legacy/unverifiable` records as rollbackable.
- Do not force-push or move release tags unless explicitly requested.

## Refusals

If SurePython refuses:

- stop the operation
- report the exact refusal
- report whether files changed
- report `git status --short`
- propose a safe next step

Never weaken a safety check to get past a refusal.

## Validation

Use the project's Python 3.12 environment:

```powershell
python -m pytest
python -m surepython scan tests\fixtures --format json
python -m surepython diff
git status --short
```

## Product Boundary

SurePython is not a general Python development engine.

It is a narrow, auditable execution tool for supported micro-changes.
````
