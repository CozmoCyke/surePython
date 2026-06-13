# SurePython Phase 1.8 Pre-Release Validation Report

## Purpose

This report records the pre-publication validation of the Phase 1.8 documentation branch.

Phase 1.8 remains documentation-only. No SurePython engine code, behavioral tests, or `pyproject.toml` settings were changed.

## Starting State

- Branch: `docs/phase-1.8`
- Starting documentation commit: `0a6583060ac7016fe37e0bb96a50518122306958`
- `origin/main`: `772df2cc86ae5f6ea9920f3bf67aa9d145792c00`
- Public tag object: `5f83dbad570bb925dcec095a8cf6cd272c06994e`
- Public tag target commit: `5e3a0591581fcc735b828688793b91eb008d5ef2`
- Worktree was clean at validation start.

## Documentation Review

Documents reviewed:

- `README.md`
- `docs/TUTORIAL_FR.md`
- `docs/CODEX_INTEGRATION.md`
- `docs/AGENTS_TEMPLATE.md`
- `docs/WINDOWS_TROUBLESHOOTING.md`
- `SUREPYTHON_PHASE_1_8_DOCUMENTATION_AUDIT.md`
- `SUREPYTHON_PHASE_1_8_DOCUMENTATION_PRODUCT_REPORT.md`

The central message remains:

```text
Codex reasons and proposes broadly.
SurePython executes only transformations it can prove.
A refusal protects the project.
```

## Documentation Corrections Made

Validation found one Markdown structure issue and one Windows validation nuance:

- `docs/AGENTS_TEMPLATE.md` had an early closing fence inside the reusable Markdown template.
- `docs/TUTORIAL_FR.md` used plain pytest commands where a Windows-safe local `--basetemp` is more reproducible.
- `docs/WINDOWS_TROUBLESHOOTING.md` now explicitly documents the case where `.pytest_tmp` itself is ACL-locked.
- `SUREPYTHON_PHASE_1_8_DOCUMENTATION_PRODUCT_REPORT.md` now includes the Windows-safe pytest basetemp recommendation.

These corrections are documentation-only.

## Python 3.12 Environment

The Windows launcher did not expose a local Python installation:

```text
py -0p -> No installed Pythons found!
py -3.12 -> No installed Python found!
```

Therefore the clean `.venv` was recreated with the available Codex runtime Python:

```text
C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe
Python 3.12.13
```

The resulting project virtual environment is:

```text
C:\dev\datasette-lab\surePython\.venv\Scripts\python.exe
Python 3.12.13
```

## Installation Result

The first editable install attempt failed because network access to PyPI was blocked while resolving build dependencies.

After explicit network approval, installation succeeded:

- `surepython 0.1.0`
- `libcst 1.8.6`
- `pytest 9.0.3`

Import validation:

```text
libcst/pytest OK
libcst 1.8.6
pytest 9.0.3
```

## Temporary Directory Validation

The repository-local ignore rules cover:

- `.venv/`
- `.tmp/`
- `.pytest_tmp/`
- `.pytest_cache/`
- `surepython.egg-info/`

Running pytest with:

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp .\.pytest_tmp
```

failed before functional test execution because pytest could not remove the `.pytest_tmp` root directory:

```text
PermissionError: [WinError 5] Accès refusé
```

This is a local Windows ACL issue, not a SurePython behavior failure.

The documented workaround succeeded:

```powershell
$env:TEMP = "$PWD\.tmp"
$env:TMP = "$PWD\.tmp"
.\.venv\Scripts\python.exe -m pytest --basetemp .\.tmp\pytest_phase_1_8_validation
```

## Test Result

Full test suite in the new `.venv`:

```text
36 passed in 42.12s
```

## Tutorial Commands Executed

The non-writing tutorial path was executed from the repository root:

```powershell
.\.venv\Scripts\python.exe -m surepython scan tests\fixtures
.\.venv\Scripts\python.exe -m surepython scan tests\fixtures --format json
.\.venv\Scripts\python.exe -m surepython scan tests\fixtures --format csv
.\.venv\Scripts\python.exe -m surepython add-docstring tests\fixtures\sample_module.py --function SampleClass.sample_method --dry-run
.\.venv\Scripts\python.exe -m surepython diff
git status --short
```

Results:

- text scan: OK
- JSON scan: OK
- CSV scan: OK
- qualified symbol confirmed: `SampleClass.sample_method`
- dry-run preview diff displayed
- no file write from dry-run
- `surepython diff`: empty
- `git status --short`: clean

## CLI Help Verification

Confirmed commands:

```powershell
.\.venv\Scripts\python.exe -m surepython --help
.\.venv\Scripts\python.exe -m surepython scan --help
.\.venv\Scripts\python.exe -m surepython add-docstring --help
.\.venv\Scripts\python.exe -m surepython diff --help
.\.venv\Scripts\python.exe -m surepython log --help
.\.venv\Scripts\python.exe -m surepython rollback --help
```

Confirmed CLI surface:

- `scan PATH --format {text,json,csv}`
- `add-docstring FILE --function FUNCTION [--test] [--test-command TEST_COMMAND] [--dry-run] [--db DB]`
- `diff`
- `log --db DB`
- `rollback --last --db DB [--dry-run]`

## CRLF Smoke Test

A separate temporary Git repository was created under:

```text
C:\dev\datasette-lab\surePython\.tmp\phase_1_8_crlf_smoke_clean
```

Scenario:

1. Created a CRLF Python file.
2. Initialized Git.
3. Committed the initial state.
4. Ran `add-docstring --test --db`.
5. Confirmed pytest status `passed`.
6. Committed the modified state.
7. Ran `rollback --last --db ... --dry-run`.
8. Confirmed dry-run showed rollback diff and did not write.
9. Ran real rollback.
10. Compared original and restored bytes.
11. Verified the SQLite rollback row.

Hashes:

```text
before_sha256     = 1d3e9b2282b7b013549b647bf7c622c9f218ddf13dd404d0565c4c740cabde21
after_add_sha256  = 410f7f1282a3660cc7227d839f5a4da24244863f5f5282c30d4328f5c794700b
restored_sha256   = 1d3e9b2282b7b013549b647bf7c622c9f218ddf13dd404d0565c4c740cabde21
bytes_equal       = True
```

SQLite rollback row:

```text
('rollback', 'rolled_back', 'SampleClass.sample_method',
 '410f7f1282a3660cc7227d839f5a4da24244863f5f5282c30d4328f5c794700b',
 '1d3e9b2282b7b013549b647bf7c622c9f218ddf13dd404d0565c4c740cabde21')
```

After rollback, the temporary smoke repository showed:

```text
M sample_module.py
```

This is expected because the rollback restored the file to the initial bytes while the temporary repository HEAD was the modified commit.

## Legacy/Unverifiable Records

The old historical manual database remains classified as:

```text
legacy/unverifiable
```

It is not used as a success test. Refusal on such records remains the correct guardrail.

## Markdown Link Check

Local Markdown links were checked with a read-only script:

```text
Markdown files scanned: 22
Local links checked: 6
All local Markdown links resolve.
```

## Engine And Test Files

No changes were made to:

- `surepython/*.py`
- `tests/*.py`
- `pyproject.toml`

The Phase 1.8 delta remains documentation-only.

## Known Limits

- The Windows `py` launcher does not currently expose a local Python 3.12 installation.
- `.pytest_tmp` can be ACL-locked in this workspace; `.tmp\<fresh-basetemp>` is the validated workaround.
- SurePython still supports only the documented micro-codemod.
- Rollback remains explicit and limited to compatible SQLite-logged `add-docstring` operations.
- Historical inconsistent records remain `legacy/unverifiable`.

## Human Review Still Required

Before transfer to `main` or a new public preview:

- human review of the product wording
- human execution or acceptance of the French tutorial flow
- decision on whether the Codex runtime Python 3.12 validation is sufficient or whether a separate system Python 3.12 install is required
- review of the Windows temporary-directory guidance
- explicit approval before any push
- explicit approval before any new tag
