# Codex Integration Policy

This document defines the relationship between Codex and SurePython.

Core rule:

```text
Codex reasons and proposes broadly.
SurePython executes only transformations it can prove.
```

## Division Of Responsibility

Codex may:

- inspect the repository
- explain code
- propose implementation plans
- write ordinary code when explicitly asked outside the SurePython safety lane
- recommend SurePython commands
- interpret SurePython refusal messages
- prepare reports and documentation

SurePython may:

- report machine-readable capabilities
- scan Python symbols
- preview a supported micro-change
- add one skeleton docstring to one function or method
- add one explicit return annotation to one function or method
- run pytest after a real edit
- record the operation in SQLite
- roll back one compatible logged `add-docstring` operation

SurePython must not be described as a general-purpose coding agent. It is a narrow executor.

## Required Workflow For Supported Operations

For a supported docstring operation, Codex should prefer:

```powershell
python -m surepython capabilities --format json
python -m surepython scan <project-or-folder> --format json
python -m surepython add-docstring <file.py> --function <symbol> --dry-run
python -m surepython add-docstring <file.py> --function <symbol> --test --db <database.db>
python -m surepython diff
git status --short
```

For a supported return annotation operation:

```powershell
python -m surepython capabilities --format json
python -m surepython scan <project-or-folder> --format json
python -m surepython add-return-type <file.py> --function <symbol> --annotation "<annotation>" --dry-run
python -m surepython add-return-type <file.py> --function <symbol> --annotation "<annotation>" --test --db <database.db>
python -m surepython diff
git status --short
```

SurePython validates annotation syntax. It does not guarantee that referenced names are imported or runtime-resolvable; Codex should rely on `--test` to expose that class of failure.

For rollback:

```powershell
python -m surepython rollback --last --db <database.db> --dry-run
python -m surepython rollback --last --db <database.db>
```

Rollback must remain explicit. Codex should not turn a pytest failure into an automatic rollback unless a future SurePython phase implements and documents that behavior.

## Agent Safety Rules

When using SurePython, an agent must:

- inspect before changing
- run `capabilities --format json` before selecting a SurePython operation
- prefer `scan --format json` when structured context is useful
- run `--dry-run` before a real operation
- keep one operation to one file and one symbol
- pass `--db` when an audit trail is expected
- treat refusal as a valid outcome
- never bypass hash checks
- never edit SQLite records to make rollback succeed
- never move the public preview tag unless explicitly requested
- never claim SurePython supports unsupported codemods
- never infer a return annotation and attribute it to SurePython
- never assume syntactic annotation validity means pytest will pass

## Refusal Handling

If SurePython refuses, Codex should report:

- the command that refused
- the refusal message
- whether any file changed
- the current `git status --short`
- the safest next option

Codex should not "fix" a refusal by weakening a guardrail. A refusal is often the correct result.

Examples:

- existing docstring: do not replace it
- dirty worktree: ask whether to commit, stash, or stop
- ambiguous symbol: use a more precise target
- hash mismatch during rollback: stop and preserve evidence
- `legacy/unverifiable` record: document the record; do not rewrite history

## Logging Policy

For auditable operations, prefer:

```powershell
python -m surepython add-docstring <file.py> --function <symbol> --test --db <database.db>
```

The manual command remains available:

```powershell
python -m surepython log --db <database.db>
```

Use the manual command only when the intent is to replay the last local operation state into a selected database. It is not a replacement for automatic logging during normal operation.

## What Codex Must Not Infer

Codex must not infer that SurePython can:

- edit arbitrary code
- add arbitrary docstrings
- infer return types
- add imports for annotations
- replace existing return annotations
- replace existing docstrings
- modify multiple files
- roll back non-SurePython changes
- roll back by reading Git history alone
- repair historical SQLite records
- guarantee rollback for records created by older or inconsistent experiments

## Current Product Boundary

SurePython's current trustworthy power is small:

```text
scan precise symbols
preview one supported edit
apply one supported edit
run pytest
log to SQLite
rollback one compatible logged edit
```

The smallness is the design. It is the quarantine chamber between an AI proposal and real Python code.
