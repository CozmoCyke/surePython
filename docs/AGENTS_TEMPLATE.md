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
- add one explicit parameter annotation to one Python function or method that has no existing parameter annotation
- add one explicit top-level import statement with one binding to one Python module file

Current supported rollback:

- rollback the latest compatible SQLite-logged `add-docstring`, `add-return-type`, `add-parameter-type`, or `add-import` operation

Current machine-readable protocol:

- request `--format json` when the agent needs a stable response envelope

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
python -m surepython add-docstring <file.py> --function <symbol> --dry-run --format json
```

For a return annotation dry-run:

```powershell
python -m surepython add-return-type <file.py> --function <symbol> --annotation "<annotation>" --dry-run
python -m surepython add-return-type <file.py> --function <symbol> --annotation "<annotation>" --dry-run --format json
```

For a parameter annotation dry-run:

```powershell
python -m surepython add-parameter-type <file.py> --function <symbol> --parameter <parameter> --annotation "<annotation>" --dry-run
python -m surepython add-parameter-type <file.py> --function <symbol> --parameter <parameter> --annotation "<annotation>" --dry-run --format json
```

For an import dry-run:

```powershell
python -m surepython add-import <file.py> --statement "<exact import statement>" --dry-run
python -m surepython add-import <file.py> --statement "<exact import statement>" --dry-run --format json
```

For a real operation:

```powershell
python -m surepython add-docstring <file.py> --function <symbol> --test --db <database.db>
python -m surepython add-docstring <file.py> --function <symbol> --test --db <database.db> --format json
python -m surepython add-return-type <file.py> --function <symbol> --annotation "<annotation>" --test --db <database.db>
python -m surepython add-return-type <file.py> --function <symbol> --annotation "<annotation>" --test --db <database.db> --format json
python -m surepython add-parameter-type <file.py> --function <symbol> --parameter <parameter> --annotation "<annotation>" --test --db <database.db>
python -m surepython add-parameter-type <file.py> --function <symbol> --parameter <parameter> --annotation "<annotation>" --test --db <database.db> --format json
python -m surepython add-import <file.py> --statement "<exact import statement>" --test --db <database.db>
python -m surepython add-import <file.py> --statement "<exact import statement>" --test --db <database.db> --format json
python -m surepython diff
git status --short
```

For rollback:

```powershell
python -m surepython rollback --last --db <database.db> --dry-run
python -m surepython rollback --last --db <database.db> --dry-run --format json
python -m surepython rollback --last --db <database.db>
python -m surepython rollback --last --db <database.db> --format json
python -m surepython rollback --id <operation_id> --db <database.db> --dry-run
python -m surepython rollback --id <operation_id> --db <database.db>
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
- Do not infer parameter annotations.
- Do not add imports automatically.
- Do not infer imports automatically.
- Do not rewrite or sort existing imports.
- Do not accept multi-binding, wildcard, or relative imports for add-import.
- Do not broaden `Class.method` into a global function edit.
- Do not broaden a parameter edit beyond the explicitly named parameter.
- Do not run rollback without `--db`.
- Do not run real rollback before rollback `--dry-run`.
- Do not pass `--last` and `--id` together.
- Do not run `--id` rollback without checking the current project context.
- Do not edit SQLite hashes to make rollback succeed.
- Do not treat `legacy/unverifiable` records as rollbackable.
- Do not force-push or move release tags unless explicitly requested.
- Do not ignore `protocol_schema_version` or `error.code` in JSON mode.

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
