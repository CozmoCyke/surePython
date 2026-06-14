# SurePython Phase 2.5 Pre-Merge Review

## Summary

Phase 2.5 is ready for transfer.

The branch adds `add-decorator` as a narrow, explicit operation and keeps the existing supported operations intact.

## State Reviewed

- Branch: `feature/phase-2.5-add-decorator`
- HEAD: `dd7a2cc86e82c7234d8ab16cbf5ca544ce2b2d88`
- Main / origin/main: `705e98a4e9d96a647f8b7958d8d2c261791835aa`
- Public tag: `v0.7.0-public-preview` -> `705e98a4e9d96a647f8b7958d8d2c261791835aa`
- Worktree: clean
- Test count: `155`
- Pushes: none
- Tags created or moved during this review: none

## Delta Inspected

The reviewed delta is limited to:

- `add-decorator` implementation
- decorator validation and explicit position handling
- capabilities registry
- JSON protocol extension
- additive SQLite columns
- rollback dispatch for decorator operations
- tests
- documentation and phase reports

No unexpected operation or broad rewrite was introduced.

## Findings

No blocking defects were found in the reviewed scope.

### Verified Behavior

- `add-decorator` targets exactly one function, method, async function, async method, or class
- decorator insertion respects `outermost` and `innermost`
- existing decorator order is preserved
- comments attached to existing decorators remain attached
- duplicate decorators are refused
- compatible decorator-family conflicts are refused
- JSON responses remain under protocol schema `1.0`
- SQLite schema changes are additive and nullable
- rollback by `--last` and `--id` remains available
- rollback is byte-exact on LF, CRLF, and BOM cases
- composition with `add-import` and return annotations is preserved

### Validation Performed

- `python -m pytest --basetemp .\.tmp\pytest_phase_2_5_final -q`
- `python -m surepython capabilities --format json`
- `python -m surepython scan surepython --format json`
- `python -m surepython diff`
- `git diff --check`
- targeted smoke tests in temporary repositories for:
  - outermost and innermost decorator placement
  - class target insertion
  - comment preservation
  - real `add-decorator --test --db`
  - `rollback --id`
  - second rollback refusal

## Self-Hosting Metrics

The phase remains honest about bootstrap boundaries:

- Python code changes done with SurePython during implementation: `0`
- Python code changes done directly by Codex: `8`
- SurePython-assisted validation and smoke proofs: yes
- Reason for fallback: `add-decorator` did not exist before the new plumbing was implemented

## Recommendation

Ready for transfer to `main`.

No correction is required before merge.
