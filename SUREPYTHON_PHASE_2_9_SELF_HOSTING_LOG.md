# SurePython Phase 2.9 Self-Hosting Log

## Scope

This phase adds `remove-import`.

The phase also updates the documentation and test coverage for the new capability.

## Change Log

| Change | Supported by SurePython? | Method used | operation_id | Result | Fallback |
| --- | --- | --- | --- | --- | --- |
| Add `remove-import` codemod plumbing | No | Direct Codex edit | n/a | Implemented | Capability did not exist yet |
| Extend rollback for `remove-import` | No | Direct Codex edit | n/a | Implemented | Capability did not exist yet |
| Extend SQLite schema and readers | No | Direct Codex edit | n/a | Implemented | Capability did not exist yet |
| Extend CLI and protocol payloads | No | Direct Codex edit | n/a | Implemented | Capability did not exist yet |
| Extend capability registry | No | Direct Codex edit | n/a | Implemented | Capability did not exist yet |
| Add regression tests for `remove-import` | No | Direct Codex edit | n/a | Implemented | Capability did not exist yet |
| Update product documentation | No | Direct Codex edit | n/a | Implemented | Documentation is outside the supported write set |

## Metrics

- Total Python file writes in this phase: 8
- Python file writes done with SurePython: 0
- Python file writes done directly: 8
- Read-only SurePython uses: 2

## Notes

The direct fallback is correct here because `remove-import` itself had to be introduced before SurePython could be used to perform that operation.

The read-only SurePython checks used during the phase were:

- `surepython capabilities --format json`
- `surepython scan surepython --format json`

## Conclusion

This phase is honest self-hosting with a controlled fallback: SurePython was used for orientation and verification, while the new operation plumbing itself was built directly.
