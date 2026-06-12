# SurePython Phase 1.5 Test Integration Report

## Objective

Add `--test` to `add-docstring` so a real micro-change can immediately run `python -m pytest` and report the result.

## What Changed

- Added a dedicated `run_pytest()` helper in `surepython/codemods.py`.
- The helper runs `python -m pytest` with `subprocess.run([sys.executable, "-m", "pytest"])` by default.
- `add-docstring --test` now runs tests only after a real edit.
- `add-docstring --dry-run` remains write-free and does not launch pytest.
- The CLI now reports the pytest exit status and returns a nonzero code when tests fail.

## Behavior

- Real edit without `--test`:
  - applies the docstring
  - prints the diff
  - does not run tests
- Real edit with `--test`:
  - applies the docstring
  - prints the diff
  - runs `python -m pytest`
  - reports success or failure
  - returns an error code if pytest fails
- Dry-run:
  - previews the diff
  - does not modify the file
  - does not run tests

## Validation

- `python -m pytest`
- `python -m surepython scan tests\fixtures --format json`
- `python -m surepython add-docstring tests\fixtures\sample_module.py --function SampleClass.sample_method --dry-run`
- `python -m surepython diff`
- `git status --short`

## Notes

- The public release tag `v0.1.2-public-preview` remains fixed on `5e3a0591581fcc735b828688793b91eb008d5ef2`.
- No rollback automation was introduced in this phase.

