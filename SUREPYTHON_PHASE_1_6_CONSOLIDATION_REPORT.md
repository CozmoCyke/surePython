# SurePython Phase 1.6 Consolidation Report

## Purpose

This report documents the current behavior introduced by commit `ef3d0f6` (`Add automatic SQLite logging`) without extending the feature set.

Phase 1.6 adds automatic SQLite logging for `add-docstring` when `--db` is supplied. The existing manual `surepython log` command remains available.

## Current Behavior

### When `add-docstring` logs automatically

`add-docstring` writes a SQLite record automatically whenever a database path is provided through `--db` or `db_path`.

The automatic write happens for:

- a real edit with no `--test`
- a real edit with `--test`
- a dry run with `--db`
- a refusal that is already detected inside the codemod flow

When `--db` is not provided, the behavior remains unchanged from the previous phase.

### Fields written to SQLite

The SQLite table `surepython_operations` currently stores:

- `created_at`
- `project_path`
- `file_path`
- `operation`
- `symbol`
- `before_sha256`
- `after_sha256`
- `git_diff`
- `pytest_command`
- `pytest_exit_code`
- `pytest_status`
- `status`
- `message`

These fields are populated from the `OperationRecord` built by `surepython/codemods.py` and written by `surepython/datasette_log.py`.

### Dry-run behavior

With `--dry-run`:

- the target file is not rewritten
- the preview diff is computed in memory
- `pytest` is not launched
- the returned status is `planned`
- if `--db` is provided, a SQLite record is written with:
  - `status = planned`
  - `git_diff =` preview diff text
  - `after_sha256 =` the pre-change hash

### Test behavior

With `--test` on a real edit:

- the docstring change is applied first
- `python -m pytest` is executed through the `run_pytest()` helper by default
- the CLI prints the pytest exit status
- the returned record includes:
  - `pytest_command`
  - `pytest_exit_code`
  - `pytest_status`
- if pytest fails, the CLI returns a nonzero exit code and the logged status becomes `failed`

### Refusals

Refusals are already logged inside the codemod flow when `--db` is supplied.

Examples of refusals currently traced:

- file does not exist
- file is outside the authorized project root
- LibCST parse failure
- target symbol not found
- target symbol already has a docstring

The refusal record uses `status = refused` and includes the refusal message.

### Pytest failures

When `--test` is used and pytest fails:

- the operation remains applied on disk
- the result status becomes `failed`
- `pytest_status = failed`
- `pytest_exit_code` captures the nonzero exit code
- the failure is stored in SQLite when `--db` is present

### Manual log command

`surepython log --db <path>` still exists.

Its role is distinct from automatic logging:

- it reads the last recorded operation from the local state file
- it inserts that record into the SQLite database at the requested path
- it is useful for explicit replay or deferred logging

Automatic `--db` logging does not replace the manual command. The manual command remains the explicit path for replaying the last operation into a chosen database.

## Contract Of Phase 1.6

- A real `add-docstring` operation must leave a SQLite trace when `--db` is provided.
- A dry run must not be recorded as an applied modification.
- A refusal must be traceable without pretending that a file changed.
- A pytest failure must be visible in the status and the pytest fields.
- The manual log command must remain available for explicit recording of a state-file operation.

## Known Limits

- No automatic rollback exists yet.
- No dedicated command exists yet to replay or undo an operation.
- There is no complete `planned` / `rolled_back` policy beyond the current phase contract.
- This phase documents the existing behavior; it does not extend it.

## Recommended Validation

```powershell
python -m pytest
python -m surepython scan tests\fixtures --format json
python -m surepython add-docstring tests\fixtures\sample_module.py --function SampleClass.sample_method --dry-run
python -m surepython diff
git status --short
```

## Notes

- Public tag `v0.1.2-public-preview` remains fixed on `5e3a0591581fcc735b828688793b91eb008d5ef2`.
- This report documents the current Phase 1.6 contract only.

