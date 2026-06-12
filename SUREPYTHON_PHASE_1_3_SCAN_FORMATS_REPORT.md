# SurePython Phase 1.3 Scan Formats Report

## Objective

Add structured outputs for `scan` without adding a new command.

## What changed

- `scan` now supports:
  - default `text`
  - `json`
  - `csv`
- The scan record shape now includes:
  - `file`
  - `type`
  - `name`
  - `qualified_name`
  - `line_start`
  - `line_end`
  - `has_docstring`
- The CLI now rejects unknown scan formats cleanly.

## Validation

- `python -m pytest`
- `python -m surepython scan tests\fixtures`
- `python -m surepython scan tests\fixtures --format json`
- `python -m surepython scan tests\fixtures --format csv`
- `python -m surepython diff`

## Notes

- `text` remains the default and preserves the human-readable scan workflow.
- JSON output is a pretty-printed list of objects.
- CSV output uses the standard library `csv` module and includes a header row.
- No changes were made to `add-docstring`, `diff`, or `log`.

