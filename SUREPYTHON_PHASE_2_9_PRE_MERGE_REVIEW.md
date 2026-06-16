# SurePython Phase 2.9 Pre-Merge Review

## Branch And Baseline

- branch: `feature/phase-2.9-remove-import`
- baseline HEAD before hardening: `4d17f9a85f130fb2b1cf47319fa06466a77d7fb4`
- `main` / `origin/main`: `f887681fa8fa13af5630c7500ca49ca740b3eaca`
- public tag: `v0.11.0-public-preview`

## Delta Inspected

The review covered the full Phase 2.9 delta:

- `remove-import` codemod implementation
- CLI wiring and JSON/text output
- SQLite schema extension
- rollback dispatch for `remove-import`
- protocol and capabilities updates
- regression and smoke tests
- product documentation and phase reports

## Findings

### Finding 1: Remove-import JSON contract used only the legacy `binding` key

The initial Phase 2.9 output for `remove-import` exposed the removed binding only as `binding`. The phase contract and review request require the public field `import_binding`.

Impact:

- public JSON contract was not fully aligned with the documented shape
- downstream agents would need to know both historical and new naming conventions

Correction applied:

- `remove-import` JSON now exposes `import_binding`
- the historical `binding` alias remains for compatibility
- tests and protocol documentation were updated accordingly

## Contract Review

Verified behavior now covers:

- exact expected import statement
- module-level scope only
- unique structural match
- ambiguous duplicate refusal
- byte-exact rollback restoration
- no import reordering or fusion
- no usage analysis
- stable JSON protocol root `1.0`
- additive SQLite schema changes

## Validation

Completed successfully after hardening:

- targeted tests: `42 passed`
- full suite: `241 passed`
- `surepython capabilities --format json`
- `surepython scan surepython --format json`
- `surepython diff`
- `git diff --check`

## Residual Risk

No blocking issue remains from the review. The remaining risk is the usual one for a phase with exact-match structural edits: future edge cases may still need explicit fixture coverage if new import syntax variations are added later.

## Recommendation

Ready for transfer after the hardening commit.
