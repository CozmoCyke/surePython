# Windows Troubleshooting

This project has been validated on Windows, including CRLF rollback behavior. Some failures are environment issues, not SurePython behavior issues.

## Python 3.12 And Broken `.venv`

Symptom:

```text
The system cannot find the path specified
```

or a `.venv\Scripts\python.exe` launcher points to a removed Python installation.

Cause:

The virtual environment was created with an interpreter path that no longer exists, for example under:

```text
C:\Users\Lenovo\AppData\Local\Programs\Python\Python312\
```

Fix:

```powershell
Remove-Item -Recurse -Force .\.venv
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pytest
```

Do not reintroduce local behavioral shims for `libcst` or `pytest` to work around a broken environment.

## Python Hermes Or Launcher Confusion

If `python` launches an unexpected shim or managed runtime, call the intended interpreter explicitly:

```powershell
.\.venv\Scripts\python.exe -m surepython --help
.\.venv\Scripts\python.exe -m pytest
```

In Codex-managed environments, a bundled runtime may be used for validation when the local `.venv` is broken. That is an environment workaround, not a SurePython behavior change.

## Pytest Temporary Directory ACLs

Symptoms can include pytest failing before tests execute because it cannot access temporary folders under:

```text
C:\Users\<user>\AppData\Local\Temp\pytest-of-<user>
```

or local `.pytest_tmp` permission issues.

Workaround:

```powershell
New-Item -ItemType Directory -Force .\.tmp
$env:TEMP = "$PWD\.tmp"
$env:TMP = "$PWD\.tmp"
.\.venv\Scripts\python.exe -m pytest --basetemp .\.tmp\pytest
```

If this fixes the run, the issue is local ACL state.

If a previously created `.pytest_tmp` directory remains ACL-locked, do not treat that as a SurePython test failure. Prefer a fresh subdirectory under `.tmp`, for example:

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp .\.tmp\pytest_phase_validation
```

## `.vendor3` And `sitecustomize.py`

Earlier phases removed root-level behavioral shims such as local fake `libcst.py` or `pytest.py`.

The remaining `.vendor3` and `sitecustomize.py`, when present, are local bootstrap infrastructure for dependency loading in this workspace. They must not be described as replacements for official packages.

## LF, CRLF, BOM, And Final Newline

Rollback must be byte-exact.

On Windows, text-mode file operations can accidentally change:

- LF versus CRLF
- final newline bytes
- UTF-8 BOM presence

SurePython rollback now reconstructs bytes in memory and writes with byte APIs only after the restored hash matches `before_sha256`.

The same byte-exact contract applies to `add-docstring`, `add-return-type`, `remove-return-type`, `add-parameter-type`, `remove-parameter-type`, `add-import`, `add-decorator`, and `remove-decorator` rollback paths.

If rollback refuses with:

```text
Rollback result does not match logged before_sha256
```

do not bypass the check. First determine whether the SQLite record is coherent.

## Historical Records: `legacy/unverifiable`

A record is `legacy/unverifiable` when:

- the current file matches logged `after_sha256`
- no reconstructible restored state matches logged `before_sha256`
- reasonable variants for encoding, BOM, LF/CRLF, and final newline do not recover the hash

Contract:

- SurePython refuses rollback
- no file is modified
- the historical hash is not replaced
- Git is not silently treated as a substitute truth source

This is a successful guardrail. It prevents SurePython from pretending to restore an operation it cannot prove.

## Rollback By ID And Project Mismatch

If `rollback --id <operation_id>` refuses with a project mismatch, the selected operation belongs to a different logged project than the current Git root. This is a safety check, not a Windows bug.

Use the repository root that matches the logged project, and confirm the operation id with:

```powershell
python -m surepython rollback --id <operation_id> --db <database.db> --dry-run --format json
```

`rollback --id` can target any supported logged micro-modification, including parameter-annotation additions and removals, explicit import insertions, explicit decorator insertions and removals, and return-annotation removal, but it still refuses legacy/unverifiable records and project mismatches.

## Clean Git Requirement

Most SurePython write paths require a clean worktree.

Check:

```powershell
git status --short
```

If it is not empty, decide explicitly whether to commit, stash, or stop. Do not let an agent work around this guardrail silently.
