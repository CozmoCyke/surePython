# SurePython Phase 2.3 Self-Hosting Log

## Summary

This phase extends the execution layer itself by introducing a new supported operation. Because the operation did not exist at the start of the phase, the write-side implementation was done directly in Codex, while SurePython was used read-only for capability discovery and symbol scanning.

## Read-Only SurePython Checks

- `python -m surepython capabilities --format json`
- `python -m surepython scan surepython --format json`

These checks confirmed the current contract before any Python code changed.

## Python Change Log

| Change | Supported by SurePython at the time? | Method used | operation_id | Result | Fallback |
|---|---|---|---|---|---|
| `surepython/codemods.py` | No | Direct Codex edit | N/A | Added `add-parameter-type` codemod and parameter validation | Feature did not exist yet |
| `surepython/datasette_log.py` | No | Direct Codex edit | N/A | Added additive `parameter` persistence | Schema work required |
| `surepython/capabilities.py` | No | Direct Codex edit | N/A | Declared the new operation and parameter kind support | Capability registry had to be extended |
| `surepython/cli.py` | No | Direct Codex edit | N/A | Added CLI dispatch and protocol payloads | New command wiring required |
| `surepython/protocol.py` | No | Direct Codex edit | N/A | Added parameter-specific refusal codes | Protocol surface had to stay stable |
| `surepython/rollback.py` | No | Direct Codex edit | N/A | Added rollback dispatch for parameter annotations | New rollback path required |
| `tests/test_add_parameter_type.py` | No | Direct Codex edit | N/A | Added feature and regression tests | No SurePython write path available |
| `tests/test_capabilities.py` | No | Direct Codex edit | N/A | Validated new capability metadata | Read-only validation only |
| `tests/test_protocol_json.py` | No | Direct Codex edit | N/A | Validated JSON envelopes for the new operation | Read-only validation only |
| `tests/test_rollback.py` | No | Direct Codex edit | N/A | Validated rollback coverage for the new operation | Read-only validation only |

## Metrics

- Total Python files changed: 10
- Changes performed with SurePython write operations: 0
- Changes performed directly: 10
- Direct fallbacks: 10

## Honest Boundary

This is not a failure of the policy. It is the correct behavior:

- the new operation did not exist yet
- SurePython cannot be asked to use a capability it has not implemented
- once merged, future parameter-annotation edits should use `add-parameter-type`

## Smoke Validation Notes

The external smoke run confirmed:

- `add-parameter-type` works in a clean temporary repository
- `--test` and `--db` produce a structured JSON result with an `operation_id`
- rollback by explicit `--id` succeeds after the temporary repository is committed clean
- rollback refused correctly when invoked from the wrong project root
- rollback refused correctly when the repository was not clean

## Conclusion

Phase 2.3 is a bootstrap phase for a new safe operation, not a self-hosting phase in the strict write-path sense.
