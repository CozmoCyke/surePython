# SurePython Phase 2.10 Implementation Report

## Summary

Phase 2.10 adds `remove-docstring`, a safe explicit docstring removal operation.

Implemented behavior:

- accepts `--symbol`
- accepts `--expect-docstring`
- supports module, class, function, and method targets
- refuses missing, mismatched, unsupported, and inline-suite docstrings
- supports `--dry-run`
- supports `--test`
- supports `--db`
- emits stable JSON with `--format json`
- records enough metadata for byte-exact rollback

## Engine Changes

The code now stores and propagates:

- expected docstring text
- removed docstring text
- removed docstring source text
- docstring target kind
- byte-exact source pre-image

Rollback for the new operation restores the logged pre-image bytes and still verifies the restored SHA-256 against `before_sha256`.

## Contract Changes

The following public surfaces were updated:

- command implementation in `surepython/cli.py`
- codemod logic in `surepython/codemods.py`
- rollback support in `surepython/rollback.py`
- SQLite schema in `surepython/datasette_log.py`
- capability registry in `surepython/capabilities.py`
- protocol error codes in `surepython/protocol.py`

## Validation

Validated locally with:

```powershell
python -m pytest --basetemp .\.tmp\pytest_phase_2_10 -q
python -m surepython capabilities --format json
python -m surepython scan surepython --format json
python -m surepython diff
git diff --check
git status --short
```

Result:

- `254 passed`
- protocol and capability JSON remain stable
- rollback remains byte-exact
- worktree stays clean after the validation run

## Notes

`remove-docstring` is intentionally narrow. It does not infer target text, does not rewrite unrelated code, and does not weaken the rollback hash check.
