# SurePython Phase 2.8 Architecture Audit

## Scope

Phase 2.8 adds `remove-decorator`, a symmetric counterpart to `add-decorator`.
The feature removes exactly one explicit decorator expression from a function,
method, or class after validating the requested decorator expression and
position.

## What Was Reused

- The existing CLI protocol, including `protocol_schema_version = "1.0"` and
  JSON/text output selection.
- The existing SQLite logging pipeline and rollback machinery.
- The existing symbol scanner and qualified-name resolution.
- The existing decorator-expression validator and CST round-tripping strategy.
- The existing dry-run, test, and rollback guardrails.

## Operation Design

`remove-decorator` is implemented as a single-symbol, single-file codemod.
It supports:

- `--symbol`
- `--expect-decorator`
- `--expect-position`
- `--dry-run`
- `--test`
- `--db`
- `--format`

The operation validates:

- file existence
- project boundary
- target existence
- target uniqueness
- decorator expression syntax
- decorator position
- decorator presence

It refuses if the requested decorator is not present, if the expected position
does not match the actual decorator position, or if the target is ambiguous or
unsupported.

## Compatibility With Existing Operations

The new codemod is added without changing the contract of:

- `add-docstring`
- `add-return-type`
- `remove-return-type`
- `remove-parameter-type`
- `add-parameter-type`
- `add-import`
- `add-decorator`
- `rollback`

Rollback support is extended additively so the new operation can be restored
byte-for-byte from the recorded decorator text and position.

## SQLite Impact

The schema change is additive and nullable.

New record fields are stored for decorator removal:

- expected decorator expression
- expected decorator position
- removed decorator expression
- removed decorator position

Old rows remain readable and old operations remain compatible.
No destructive migration was introduced.

## Risks Considered

- Removing the wrong decorator in repeated or stacked decorator lists.
- Preserving exact byte layout across LF, CRLF, BOM, and final-newline variants.
- Preserving rollback fidelity for historical logs.
- Preserving JSON protocol stability for agents.

The implementation mitigates these risks by recording the exact decorator text
and position, validating the requested expression, and reusing the same
byte-exact rollback helpers that already protect the other codemods.

## Conclusion

The architecture remains a small, explicit set of safe transformations with a
shared protocol, shared log, and shared rollback mechanism.
`remove-decorator` extends the system without widening the trust boundary.
