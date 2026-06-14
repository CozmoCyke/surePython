# SurePython Phase 2.5 Self-Hosting Log

## Summary

Phase 2.5 introduced a new operation, `add-decorator`. Because the operation did not exist yet, the new plumbing was implemented directly in Codex and then validated with SurePython.

## Metrics

- Total Python code edits in this phase: `8` files
- Python code edits performed through SurePython: `0`
- Python code edits performed directly: `8`
- Direct fallbacks were required because `add-decorator` was not yet available before the plumbing existed.

## Change Log

| Change | SurePython-supported? | Method used | operation_id | Result | Fallback |
| --- | --- | --- | --- | --- | --- |
| `surepython/codemods.py` add-decorator implementation | No, capability did not exist yet | Direct Codex edit | n/a | Implemented successfully | Required to create the new operation |
| `surepython/cli.py` command wiring | No, capability did not exist yet | Direct Codex edit | n/a | Implemented successfully | Required to expose the new command |
| `surepython/protocol.py` error-code extension | No, capability did not exist yet | Direct Codex edit | n/a | Implemented successfully | Required to keep JSON stable |
| `surepython/datasette_log.py` additive schema support | No, capability did not exist yet | Direct Codex edit | n/a | Implemented successfully | Required to log and rollback decorators |
| `surepython/rollback.py` decorator rollback support | No, capability did not exist yet | Direct Codex edit | n/a | Implemented successfully | Required to restore decorator edits byte-for-byte |
| `surepython/capabilities.py` capability registry update | No, capability did not exist yet | Direct Codex edit | n/a | Implemented successfully | Required to advertise the new operation |
| `tests/test_add_decorator.py` and protocol/capabilities regression tests | No, capability did not exist yet | Direct Codex edit | n/a | Implemented successfully | Required to prove the new path |
| Validation via `capabilities`, `scan`, dry-run JSON, and smoke rollback | Yes | SurePython commands | `1` on smoke add, `2` on rollback | Passed | None |

## Smoke Proof

A temporary Windows smoke repository validated the happy path:

- `add-decorator --test --db` returned `operation_id = 1`
- rollback by `--id 1` returned `rollback_operation_id = 2`
- `bytes_equal = true`
- a second rollback attempt returned `ROLLBACK_ALREADY_APPLIED`

## Honest Boundary

SurePython was used aggressively for validation and proof, but not for the first implementation of the new operation. That is the correct boundary: an operation must exist before it can be used as the guardrail for itself.
