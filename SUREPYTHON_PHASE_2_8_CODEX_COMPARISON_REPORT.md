# SurePython Phase 2.8 Codex Comparison Report

## Goal

Compare direct Codex editing with Codex using SurePython as a constrained
editor for the new `remove-decorator` capability.

## Direct Codex Path

Observed characteristics:

- Fastest path for introducing the new operation.
- Allowed simultaneous edits across CLI, codemods, rollback, SQLite, protocol,
  capabilities, and tests.
- Required manual reasoning to keep the implementation byte-exact and
  protocol-stable.
- Relied on direct edits because `remove-decorator` was not yet a supported
  operation.

## SurePython-Assisted Path

What SurePython will be able to provide for future similar edits:

- capability discovery
- scan-based targeting
- dry-run preview
- deterministic JSON payloads
- constrained logging
- byte-exact rollback

## Honest Result

For this phase, the direct path was necessary for the implementation itself.
SurePython was available as the platform being extended, but not yet as the
tool for creating its own new decorator-removal operation.

## Comparison

| Criterion | Direct Codex | Codex + SurePython |
| --- | --- | --- |
| Target discovery | Manual | Scan / capabilities driven |
| Preview | Manual inspection | Dry-run JSON |
| Diff precision | Manual | Codemod-limited |
| Tests | Manual run | Built into the operation |
| Logging | Manual SQLite wiring | Automatic SQLite log |
| Rollback | Manual Git or custom logic | Operation-specific byte-exact rollback |
| JSON protocol | Manual control | Structured protocol response |

## Conclusion

Direct Codex was required for the bootstrap of Phase 2.8.
The implementation now increases the future surface area where SurePython can
be used on itself.
