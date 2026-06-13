# SurePython Phase 2.2 Pre-Merge Review

Repository: `C:\dev\datasette-lab\surePython`

Branch: `feature/phase-2.2-rollback-by-id-self-hosting`

HEAD reviewed: `5e0257f631e7f7363906d9d8048adcbd0f1decb0`

Baseline:

- `main`: `6dfd3475e2ae023866cd37555d6f585c973fac3a`
- `origin/main`: `6dfd3475e2ae023866cd37555d6f585c973fac3a`
- tag `v0.4.0-public-preview`: `6dfd3475e2ae023866cd37555d6f585c973fac3a`
- protocol schema: `1.0`
- capabilities schema: `1.0`

## Scope of Review

This review checks whether Phase 2.2 is safe to transfer to `main` without further code changes.

The review covered:

- explicit rollback selection by `--id`
- compatibility of `--last`
- selector exclusivity
- refusal behavior for invalid ids and already-rolled-back operations
- project boundary checks
- SQLite migration compatibility
- JSON protocol stability
- byte-exact rollback behavior on LF, CRLF, BOM, and end-of-file preservation
- self-hosting evidence
- comparison between direct editing and SurePython-assisted editing

## Delta Inspected

The Phase 2.2 delta is limited to:

- `surepython/capabilities.py`
- `surepython/cli.py`
- `surepython/datasette_log.py`
- `surepython/protocol.py`
- `surepython/rollback.py`
- `tests/test_capabilities.py`
- `tests/test_protocol_json.py`
- `tests/test_rollback.py`
- `README.md`
- `docs/AGENTS_TEMPLATE.md`
- `docs/CODEX_INTEGRATION.md`
- `docs/PROTOCOL_JSON.md`
- `docs/TUTORIAL_FR.md`
- `docs/WINDOWS_TROUBLESHOOTING.md`
- `docs/SELF_HOSTING.md`
- `SUREPYTHON_PHASE_2_2_ARCHITECTURE_AUDIT.md`
- `SUREPYTHON_PHASE_2_2_IMPLEMENTATION_REPORT.md`
- `SUREPYTHON_PHASE_2_2_SELF_HOSTING_LOG.md`
- `SUREPYTHON_PHASE_2_2_CODEX_COMPARISON_REPORT.md`
- `AGENTS.md`

No additional codemod was introduced.
No tag was created or moved.

## Selection by Operation ID

Verified behavior:

- `rollback --id 2` selects only operation id `2`
- a newer operation does not affect selection
- the rollback target is isolated to the requested record

Smoke proof:

- operation `1`: `add-docstring` on `a.py`
- operation `2`: `add-return-type` on `b.py`
- operation `3`: `add-docstring` on `c.py`
- `rollback --id 2` restored only `b.py`
- `a.py` and `c.py` remained byte-for-byte unchanged

## `--last` Compatibility

`rollback --last` keeps its historical behavior:

- it remains available
- it remains strict about Git cleanliness
- it still refuses unsupported, unknown, legacy, or hash-inconsistent histories

The new selector does not weaken the old one.

## Selector Exclusivity

`--last` and `--id` are mutually exclusive.

This was verified by the protocol and CLI tests, and the JSON refusal path remains structured and non-destructive.

## Refusal Handling

Verified refusal cases:

- zero, negative, and missing ids
- nonexistent ids
- ids corresponding to rollback rows
- rollback already applied
- project mismatch
- Git dirty refusal
- `UNKNOWN_SQLITE_OPERATION`
- `HASH_MISMATCH`
- `LEGACY_UNVERIFIABLE`
- selector conflict between `--last` and `--id`

The explicit double-rollback refusal was confirmed with:

- first rollback by id: succeeds
- second rollback of the same source id: `ROLLBACK_ALREADY_APPLIED`

No extra write occurred on the refused second rollback.

## SQLite Compatibility

The `source_operation_id` migration is additive and idempotent.

It remains compatible with:

- Phase 1.x histories
- Phase 2.0 histories
- Phase 2.1 histories

Historical rows remain readable. The migration does not delete or rewrite old records destructively.

## JSON Protocol

The protocol remains rooted at schema version `1.0`.

The rollback JSON envelope is deterministic and machine-readable, including:

- `selector.type`
- `selector.value`
- `source_operation_id`
- `rollback_operation_id`
- `bytes_equal`

The command output stays structured JSON when requested and does not pollute stdout.

## Byte-Exact Rollback

Verified rollback behavior:

- LF preserved
- CRLF preserved
- BOM preserved
- trailing newline preserved
- restored bytes equal logged `before_sha256`

The CRLF smoke validated:

- `add-return-type --test --db`
- `rollback --id`
- byte-for-byte restoration
- double rollback refusal

## Self-Hosting Review

The self-hosting evidence is honest and mixed.

Counts for this phase:

- total Python gestures considered: `16`
- gestures covered by SurePython capability: `1`
- gestures actually executed with SurePython: `1`
- direct fallbacks: `15`
- real self-hosting coverage: `6.25%`

Interpretation:

- the SurePython repo itself was updated mostly by direct editing because the required capabilities did not yet exist at the time of the work
- SurePython was used successfully in the temporary comparison repo for one supported micro-change plus explicit rollback proof
- the work was not 100% self-hosted, and this report does not claim otherwise

## Codex Direct vs SurePython Comparison

The comparison remains honest:

Direct editing:

- shortest path
- no structured preview envelope
- no operation id
- no SQLite audit trail
- rollback is Git-level only

SurePython-assisted editing:

- capabilities query first
- scan to locate the exact symbol
- dry-run JSON preview
- explicit apply with `--test --db`
- operation id recorded
- rollback by id
- byte-exact restoration proof
- duplicate rollback refusal

Conclusion:

- direct editing is faster
- SurePython is stronger on proof, selection, logging, and reversibility

## Findings

No blocking defect was found in the Phase 2.2 implementation.

Observed behavior matches the intended contract:

- explicit rollback by id works
- `--last` remains compatible
- JSON remains stable
- migration is additive
- rollback is byte-exact
- double rollback is refused

## Validation Performed

Completed validation:

- `python -m pytest --basetemp .\\.tmp\\pytest_phase_2_2_pre_merge`
- `python -m surepython capabilities --format json`
- `python -m surepython scan surepython --format json`
- `python -m surepython diff`
- `git diff --check`
- targeted smoke for `rollback --id` selection across three operations
- targeted smoke for double rollback refusal

Results:

- `80` tests passed
- `rollback --id` selected only the requested source operation
- `rollback --id` restored only the requested file
- second rollback of the same operation was refused with `ROLLBACK_ALREADY_APPLIED`

## Recommendation

Ready for transfer to `main` as-is.

No code correction is required before merge.
The next step should be a fast-forward transfer, followed by normal validation on `main`.
