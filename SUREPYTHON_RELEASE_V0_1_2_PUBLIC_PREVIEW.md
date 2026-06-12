# SurePython v0.1.2 Public Preview

## Repository

- GitHub: https://github.com/CozmoCyke/surePython
- Tag: `v0.1.2-public-preview`
- Tagged commit: `5e3a059` - `Add GitHub publication report`

## Phase Summary

- v0.1: minimal secure pipeline
- v0.1.1: official dependencies, behavioral shims removed
- v0.1.2: explicit `Class.method` targeting

## Available Commands

- `scan`
- `add-docstring`
- `diff`
- `log`

## Known Validation

- `python -m pytest` -> 9 tests passed
- `python -m surepython scan tests\fixtures` -> OK
- `python -m surepython diff` -> OK

## Known Limits

- The tool is still experimental.
- No `scan --format json` yet.
- No `dry-run` yet.
- No automated rollback yet.

## Next Recommended Step

- Phase 1.3: `scan --format json/csv`

