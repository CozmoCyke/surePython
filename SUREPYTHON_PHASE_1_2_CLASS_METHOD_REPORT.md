# SurePython Phase 1.2 Class.Method Report

## Objective

Add explicit support for `Class.method` targets in `add-docstring` without broadening the modification surface.

## What changed

- Expanded the fixture module to include:
  - a global `sample_method`
  - `SampleClass.sample_method`
  - `OtherClass.sample_method`
- Added regression tests proving:
  - `SampleClass.sample_method` receives the skeleton docstring
  - the global `sample_method` is not modified
  - `OtherClass.sample_method` is not modified
  - an already documented method is refused
  - an unknown class is refused
  - an unknown method is refused
  - an unqualified ambiguous method name is refused
- Updated `README.md` with the explicit `Class.method` example

## Code-path assessment

The existing `surepython/codemods.py` and `surepython/scanner.py` already supported qualified symbol matching and class-scoped LibCST insertion, so no functional expansion of the modification pipeline was needed beyond the additional regression coverage.

## Validation

- `python -m pytest` -> 9 passed
- `python -m surepython scan tests\fixtures` -> passes and shows qualified class-method symbols
- `python -m surepython diff` -> shows only the intentional working-tree diff for this phase
- `git status --short` -> clean after commit once the phase is committed

## Notes

This phase kept the same safety posture:

- one file per operation
- one symbol per operation
- clean git requirement
- refusal on ambiguity
- no CSV support
- no new command surface

