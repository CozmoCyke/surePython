# SurePython Phase 2.7 Implementation Report

## Summary

Phase 2.7 adds `remove-parameter-type`, a compare-and-remove operation that removes exactly one explicit parameter annotation after verifying the expected annotation.

## What Changed

- added the `remove-parameter-type` CLI command
- added a dedicated LibCST codemod for parameter annotation removal
- extended rollback support to restore parameter annotation removals byte-exactly
- extended SQLite logging with additive nullable fields for parameter-removal metadata
- extended the capabilities registry and JSON protocol
- added regression coverage for signatures, refusal paths, rollback, logging, and composition
- updated the product documentation and agent policies

## Supported Behavior

`remove-parameter-type` supports:

- functions and methods
- positional-only, positional-or-keyword, and keyword-only parameters
- `self` and `cls`
- dry-run preview
- `--test`
- SQLite logging with `--db`
- rollback by `--last` and by `--id`

It refuses:

- missing parameters
- missing annotations
- invalid or empty expected annotations
- mismatched annotations
- `*args` and `**kwargs`
- dirty worktrees
- wrong projects
- hash mismatches
- legacy / unverifiable rollback histories

## Validation

Validated with:

- `python -m pytest`
- `python -m surepython capabilities --format json`
- `python -m surepython scan surepython --format json`
- `python -m surepython diff`
- `git diff --check`

Final test result:

- `194 passed`

## Files Changed

- `surepython/codemods.py`
- `surepython/cli.py`
- `surepython/datasette_log.py`
- `surepython/rollback.py`
- `surepython/protocol.py`
- `surepython/capabilities.py`
- `tests/test_capabilities.py`
- `tests/test_remove_parameter_type.py`
- `README.md`
- `AGENTS.md`
- `docs/CODEX_INTEGRATION.md`
- `docs/AGENTS_TEMPLATE.md`
- `docs/PROTOCOL_JSON.md`
- `docs/SELF_HOSTING.md`
- `docs/TUTORIAL_FR.md`
- `docs/WINDOWS_TROUBLESHOOTING.md`

## Notes

The new operation is narrowly scoped on purpose. It does not infer annotations, does not modify more than one parameter, and preserves the rest of the signature and file bytes.
