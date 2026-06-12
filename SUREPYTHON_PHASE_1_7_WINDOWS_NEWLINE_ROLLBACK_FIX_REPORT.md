# SurePython Phase 1.7 Windows Newline Rollback Fix Report

## Problem

The initial Phase 1.7 rollback could produce the correct logical source code while still failing `before_sha256`.

The observed failure was:

```text
Rollback result does not match logged before_sha256
```

The dry-run found the right operation and displayed the expected diff, but the real rollback refused because reconstruction was not byte-identical.

## Root Cause

Rollback used text-mode file APIs during reconstruction.

On Windows, text-mode reads can normalize line endings and text-mode writes can change the byte representation. That can alter:

- LF versus CRLF endings
- final newline bytes
- UTF-8 BOM presence

For rollback, logical equivalence is not enough. The reconstructed bytes must match the logged `before_sha256`.

## Fix

Rollback now:

- reads the target file with `read_bytes()`
- decodes UTF-8 explicitly while preserving BOM state
- builds rollback output in memory
- generates byte candidates for the supported newline/BOM variants
- selects only the candidate whose SHA-256 equals `before_sha256`
- writes with `write_bytes()` only after the candidate hash has already been validated

The `before_sha256` check remains mandatory and was not weakened.

## Dry-run Contract

Dry-run now exercises the same byte reconstruction path as real rollback.

That means dry-run must prove that a byte-exact rollback candidate exists before reporting success.

## Regression Tests Added

- exact rollback of LF files
- exact rollback of CRLF files
- preservation of the final newline
- refusal when restored bytes do not match `before_sha256`
- dry-run without writing
- clean repository after refusal
- Windows-style smoke test: add-docstring, commit, real rollback

## Validation

```powershell
python -m pytest
python -m surepython scan tests\fixtures --format json
python -m surepython diff
git status --short
```

## Notes

- No rollback approximation was introduced.
- No automatic rollback was introduced.
- Public tag `v0.1.2-public-preview` remains fixed on `5e3a0591581fcc735b828688793b91eb008d5ef2`.

