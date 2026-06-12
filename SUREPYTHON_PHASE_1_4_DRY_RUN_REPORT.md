# SurePython Phase 1.4 Dry Run Report

## Objective

Add `--dry-run` to `add-docstring` so SurePython can preview a micro-modification without writing to disk.

## What changed

- `add-docstring` now accepts `--dry-run`
- Dry run performs the same target resolution and safety checks
- Dry run builds the transformed code in memory
- Dry run prints a preview diff
- Dry run does not modify the target file on disk
- Dry run does not leave changes in `git diff`

## Validation

- `python -m pytest`
- `python -m surepython scan tests\fixtures --format json`
- `python -m surepython add-docstring tests\fixtures\sample_module.py --function SampleClass.sample_method --dry-run`
- `python -m surepython diff`

## Notes

- Normal `add-docstring` behavior remains unchanged.
- `Class.method` targeting remains intact.
- Dry run refuses already documented methods the same way the real operation does.
- No changes were made to `scan`, `diff`, or `log` beyond keeping the existing behavior stable.

