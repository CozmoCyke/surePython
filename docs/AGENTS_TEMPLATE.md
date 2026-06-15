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
- remove one explicit return annotation from one Python function or method after verifying the expected annotation
- add one explicit parameter annotation to one Python function or method that has no existing parameter annotation
- remove one explicit parameter annotation from one Python function or method after verifying the expected annotation
- add one explicit top-level import statement with one binding to one Python module file
- add one explicit decorator expression to one Python function, method, or class
- remove one explicit decorator expression from one Python function, method, or class after verifying the expected expression and position

Current supported rollback:

- rollback the latest compatible SQLite-logged `add-docstring`, `add-return-type`, `remove-return-type`, `add-parameter-type`, `add-import`, `add-decorator`, or `remove-decorator` operation

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

For a return annotation removal dry-run:

```powershell
python -m surepython remove-return-type <file.py> --function <symbol> --expect-annotation "<annotation>" --dry-run
python -m surepython remove-return-type <file.py> --function <symbol> --expect-annotation "<annotation>" --dry-run --format json
```

For a parameter annotation dry-run:

```powershell
python -m surepython add-parameter-type <file.py> --function <symbol> --parameter <parameter> --annotation "<annotation>" --dry-run
python -m surepython add-parameter-type <file.py> --function <symbol> --parameter <parameter> --annotation "<annotation>" --dry-run --format json
```

For a parameter annotation removal dry-run:

```powershell
python -m surepython remove-parameter-type <file.py> --function <symbol> --parameter <parameter> --expect-annotation "<annotation>" --dry-run
python -m surepython remove-parameter-type <file.py> --function <symbol> --parameter <parameter> --expect-annotation "<annotation>" --dry-run --format json
```

For an import dry-run:

```powershell
python -m surepython add-import <file.py> --statement "<exact import statement>" --dry-run
python -m surepython add-import <file.py> --statement "<exact import statement>" --dry-run --format json
```

For a decorator dry-run:

```powershell
python -m surepython add-decorator <file.py> --symbol <symbol> --decorator "<expression>" --position outermost --dry-run
python -m surepython add-decorator <file.py> --symbol <symbol> --decorator "<expression>" --position outermost --dry-run --format json
```

For a real operation:

```powershell
python -m surepython add-docstring <file.py> --function <symbol> --test --db <database.db>
python -m surepython add-docstring <file.py> --function <symbol> --test --db <database.db> --format json
python -m surepython add-return-type <file.py> --function <symbol> --annotation "<annotation>" --test --db <database.db>
python -m surepython add-return-type <file.py> --function <symbol> --annotation "<annotation>" --test --db <database.db> --format json
python -m surepython remove-return-type <file.py> --function <symbol> --expect-annotation "<annotation>" --test --db <database.db>
python -m surepython remove-return-type <file.py> --function <symbol> --expect-annotation "<annotation>" --test --db <database.db> --format json
python -m surepython add-parameter-type <file.py> --function <symbol> --parameter <parameter> --annotation "<annotation>" --test --db <database.db>
python -m surepython add-parameter-type <file.py> --function <symbol> --parameter <parameter> --annotation "<annotation>" --test --db <database.db> --format json
python -m surepython remove-parameter-type <file.py> --function <symbol> --parameter <parameter> --expect-annotation "<annotation>" --test --db <database.db>
python -m surepython remove-parameter-type <file.py> --function <symbol> --parameter <parameter> --expect-annotation "<annotation>" --test --db <database.db> --format json
python -m surepython add-import <file.py> --statement "<exact import statement>" --test --db <database.db>
python -m surepython add-import <file.py> --statement "<exact import statement>" --test --db <database.db> --format json
python -m surepython add-decorator <file.py> --symbol <symbol> --decorator "<expression>" --position outermost --test --db <database.db>
python -m surepython add-decorator <file.py> --symbol <symbol> --decorator "<expression>" --position outermost --test --db <database.db> --format json
python -m surepython remove-decorator <file.py> --symbol <symbol> --expect-decorator "<expression>" --expect-position outermost --test --db <database.db>
python -m surepython remove-decorator <file.py> --symbol <symbol> --expect-decorator "<expression>" --expect-position outermost --test --db <database.db> --format json
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
- Do not remove a return annotation unless the expected annotation matches.
- Do not infer return annotations.
- Do not infer parameter annotations.
- Do not remove a parameter annotation unless the expected annotation matches.
- Do not add imports automatically.
- Do not infer imports automatically.
- Do not infer decorator expressions automatically.
- Do not change decorator position implicitly.
- Do not remove a decorator unless the expected expression and position both match.
- Do not rewrite or sort existing imports.
- Do not accept multi-binding, wildcard, or relative imports for add-import.
- Do not use add-decorator to edit more than one target.
- Do not use remove-decorator to edit more than one target.
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
