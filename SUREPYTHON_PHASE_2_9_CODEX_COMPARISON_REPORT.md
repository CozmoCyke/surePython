# SurePython Phase 2.9 Codex Comparison Report

## Goal

Compare the direct Codex editing path with the SurePython-assisted path for the phase goal.

## Outcome

For the new `remove-import` plumbing, direct edits were the only honest option because the capability did not exist yet.

SurePython was still used for:

- capability discovery
- scan-based orientation
- JSON validation
- regression testing

## Direct Codex Path

Used for:

- implementing the new codemod
- extending rollback
- extending the SQLite schema
- extending the CLI and protocol payloads
- updating tests
- updating documentation

Characteristics:

- shortest path for brand-new plumbing
- full control over architecture
- no intermediate self-hosting operation id
- required careful manual review to preserve byte-exact rollback semantics

## SurePython-Assisted Path

Not available for the new write operation itself because `remove-import` was not yet part of the supported capability set.

If the capability had already existed, the assisted path would have been:

- `capabilities --format json`
- `scan --format json`
- `remove-import --dry-run --format json`
- `remove-import --test --db ...`
- `rollback --id ...`

## Honest Metrics

- Total Python write changes in the phase: 8
- SurePython-assisted Python write changes: 0
- Direct Python write changes: 8
- SurePython read-only checks: 2

## What The Comparison Shows

The direct path was necessary for the new plumbing, but the product now gains a supported operation that future phases can use through the safer assisted loop.

The useful product difference is not speed:

- SurePython gives exact targeting, preview, logging, and rollback once the capability exists
- direct edits remain the correct fallback for the code that creates a new capability

## Conclusion

Phase 2.9 is a correct boundary case: the capability introduction itself was direct, but the resulting toolset now extends the safe-operable surface for future work.
