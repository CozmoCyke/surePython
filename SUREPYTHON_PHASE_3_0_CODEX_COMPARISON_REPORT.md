# SurePython Phase 3.0 Codex Comparison Report

## Question

How does direct Codex editing compare with SurePython-assisted editing for this phase?

## Honest Answer

For the phase 3.0 bootstrap work, direct editing was required.
The new `plan` capability did not exist at the beginning of the work, so SurePython could not have been used to build the plan engine itself.

That makes the comparison asymmetrical:

- direct Codex edits were the correct method for introducing the new transactional plumbing
- SurePython becomes the preferred method only after the capability exists

## Direct Edit Strengths

- immediate access to new architecture
- no bootstrap dependency on an absent capability
- easy to iterate across the plan engine, storage, CLI, protocol, tests, and docs in one pass

## SurePython Strengths Once Available

For future grouped changes, SurePython should provide:

- capability discovery before editing
- scan-driven targeting
- preview hashes before apply
- grouped SQLite logging
- grouped rollback by `--last` or `--id`
- recovery support for interrupted transactions

## What Was Measured

The comparison criteria remain the same as in earlier phases:

- targeted precision
- preview quality
- diff readability
- pytest usage
- logging trail
- rollback evidence
- JSON contract clarity

## Result

During bootstrap:

- direct edit wins for capability creation

After bootstrap:

- SurePython wins for auditable grouped execution

## Recommendation

Use direct edits only for building new SurePython plumbing.
Use `plan preview` / `plan apply` / `plan rollback` / `plan recover` for subsequent grouped edits that fall within the new capability set.
