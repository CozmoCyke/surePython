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
- first attempts to remove the exact docstring line from the current byte stream
- generates byte candidates for the supported newline/BOM variants
- selects only the candidate whose SHA-256 equals `before_sha256`
- writes with `write_bytes()` only after the candidate hash has already been validated

The `before_sha256` check remains mandatory and was not weakened.

## Dry-run Contract

Dry-run now exercises the same byte reconstruction path as real rollback.

That means dry-run must prove that a byte-exact rollback candidate exists before reporting success.

## Historical Records: Legacy/Unverifiable

A historical record is `legacy/unverifiable` when:

- the current file matches the logged `after_sha256`
- no reconstructible state matches the logged `before_sha256`
- reasonable byte candidates for encoding, BOM, LF/CRLF endings, and final newline do not recover that hash

Contract:

- SurePython refuses the rollback
- SurePython does not modify the file
- SurePython does not replace the historical hash
- SurePython does not choose the Git blob as a substitute source of truth
- the refusal is a successful guardrail, not a failure of the current rollback implementation

These records may come from older experiments, incomplete logs, or inconsistent historical state. They must not be made valid retroactively.

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
