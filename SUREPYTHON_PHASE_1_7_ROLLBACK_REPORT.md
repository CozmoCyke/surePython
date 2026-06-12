# SurePython Phase 1.7 Rollback Report

## Objective

Add an explicit, minimal rollback command for logged SurePython operations.

Phase 1.7 only supports rolling back the latest SQLite-logged `add-docstring` operation.

## Command

```powershell
python -m surepython rollback --last --db .\surepython_lab.db --dry-run
python -m surepython rollback --last --db .\surepython_lab.db
```

## Scope

Supported:

- latest applicable `add-docstring` operation from SQLite
- statuses `applied`, `tested`, and `failed`
- rollback dry-run
- rollback of one operation at a time
- rollback logging with status `rolled_back`

Not supported:

- rollback without `--db`
- rollback of multiple operations
- rollback by date range
- rollback of non-SurePython changes
- rollback through Git history
- approximate restoration

## Safety Checks

Rollback refuses unless:

- a database path is provided
- a compatible logged `add-docstring` operation exists
- the logged operation has `file_path`, `symbol`, `before_sha256`, and `after_sha256`
- the project is a clean git repository
- the target file exists
- the target file is inside the logged project
- the current file hash matches the logged `after_sha256`
- removing the SurePython skeleton docstring restores the logged `before_sha256`

## Restoration Strategy

SurePython does not restore arbitrary file content.

For the supported operation, rollback removes only this exact skeleton docstring from the logged target symbol:

```python
"""TODO: Document this function."""
```

The rollback is accepted only if the resulting file hash matches the logged `before_sha256`.

## Dry-run Behavior

With `--dry-run`:

- the database is read
- the same safety checks are performed
- the rollback diff is printed
- the target file is not written
- no rollback record is inserted

## Real Rollback Behavior

Without `--dry-run`:

- the target file is rewritten
- the restored hash is checked against `before_sha256`
- a SQLite record is inserted with:
  - `operation = rollback`
  - `status = rolled_back`
  - `before_sha256 =` current hash before rollback
  - `after_sha256 =` restored hash after rollback
  - `git_diff =` rollback diff

## Validation

```powershell
python -m pytest
python -m surepython scan tests\fixtures --format json
python -m surepython diff
git status --short
```

## Notes

- Public tag `v0.1.2-public-preview` remains fixed on `5e3a0591581fcc735b828688793b91eb008d5ef2`.
- No automatic rollback was introduced.
- The rollback command is explicit and database-backed.

