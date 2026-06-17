# SurePython Phase 3.0 Pre-Merge Review

## Summary

Phase 3.0 was reviewed and hardened before merge. The transactional plan workflow is now validated end to end for preview, apply, rollback, recovery, and structured error reporting.

## HEAD and Branch

- Branch: `feature/phase-3.0-transactional-plans`
- HEAD: `a12bd71d1dab3f4ee80118b5ce7d8f6ef84ceb4d`
- `main`: unchanged
- `origin/main`: unchanged
- Tag `v0.13.0-public-preview`: unchanged

## Findings

Two review issues were found and corrected:

1. `plan apply` did not reject a missing preview hash through the protocol layer. It now raises `PLAN_PREVIEW_HASH_REQUIRED` instead of relying on argparse.
2. `plan rollback` did not distinguish missing selectors from selector conflicts in the structured protocol. It now returns:
   - `PLAN_INVALID` when no selector is provided
   - `ROLLBACK_SELECTOR_CONFLICT` when both selectors are provided

Additional hardening was applied during review:

- step failures inside plan simulation now surface as `PLAN_STEP_FAILED`
- the temporary simulation state file now lives outside the staging git tree, so it no longer pollutes the final plan diff

## Contract Checks

The review verified the following behavior:

- invalid plan JSON and malformed structures are rejected cleanly
- step validation is sequential and side-effect free during preview
- preview hashes are deterministic and sensitive to step order
- `plan apply` requires `--expect-preview-hash`
- plan rollback selector validation is structured and deterministic
- plan step failures are reported with step index, step id, and operation
- no-final-changes plans are refused
- recovery-required plans are refused
- rollback remains byte-exact for transactional plans
- structured JSON remains rooted at protocol schema `1.0`
- capability output remains rooted at capabilities schema `1.0`
- SQLite plan history remains additive and compatible

## Validation

Completed validation:

- `python -m pytest -q`
- `python -m surepython capabilities --format json`
- `python -m surepython scan surepython --format json`
- `python -m surepython diff`
- `git diff --check`
- `git status --short`

Final test result:

- `289 passed`

## Residual Risks

- Phase 3.0 still relies on the existing transactional manifest/recovery model.
- The plan subsystem is intentionally additive and still experimental.

## Recommendation

Ready for transfer.
