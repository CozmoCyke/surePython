# SurePython Phase 2.3 Architecture Audit

## Scope

This audit covers the architecture changes needed to add `add-parameter-type` as a third safe codemod while preserving the existing contracts for `add-docstring`, `add-return-type`, structured JSON, SQLite logging, and rollback.

## Files Audited

- `surepython/cli.py`
- `surepython/codemods.py`
- `surepython/capabilities.py`
- `surepython/datasette_log.py`
- `surepython/protocol.py`
- `surepython/rollback.py`
- `tests/test_add_parameter_type.py`
- `tests/test_capabilities.py`
- `tests/test_protocol_json.py`
- `tests/test_rollback.py`

## Architecture Findings

### Shared Pipeline

The current architecture already has a reusable control lane:

1. inspect Git cleanliness and project scope
2. resolve one qualified symbol
3. build a preview with LibCST
4. apply the exact textual change
5. optionally run pytest
6. emit a JSON protocol envelope when requested
7. record the operation in SQLite
8. support explicit rollback from logged state

`add-parameter-type` fits that lane without needing a new command family or a new transport layer.

### Reused Logic

`add-parameter-type` reuses:

- Git root and cleanliness checks
- symbol resolution and ambiguity detection
- the shared SQLite write path
- the stable JSON protocol envelope
- rollback dispatch and byte-exact reconstruction logic

### New Logic

The new operation needs only narrow additions:

- explicit `--parameter`
- parameter kind validation
- refusal for variadic parameters
- parameter-specific LibCST transformation
- parameter-specific SQLite provenance

### Capability Registry

The existing capability registry is the right place to declare the new operation because agents need a machine-readable contract before choosing a tool.

The registry now needs to expose:

- operation name
- supported target kinds
- required arguments
- supported and unsupported parameter kinds
- dry-run/test/log/rollback support
- stable error codes

### SQLite Compatibility

The schema change is additive:

- new nullable `parameter` column
- legacy rows remain readable
- previous rollback rows remain valid
- the new field can be absent or `NULL` for non-parameter operations

This preserves Phase 1.x, 2.0, 2.1, and 2.2 databases without destructive migration.

### Rollback Compatibility

Rollback can dispatch by operation type:

- `add-docstring`
- `add-return-type`
- `add-parameter-type`

The rollback selector and the source-operation row both need to carry parameter provenance when the source operation is parameter-based.

## Risk Assessment

Main risks:

- duplicating function/method targeting logic
- weakening annotation validation
- silently accepting variadic parameters
- regressing JSON payload shape
- breaking compatibility with older SQLite rows

Mitigations:

- keep the new codemod as a thin sibling of the existing two codemods
- reuse the same preview/apply/test/log sequence
- require explicit parameter names
- refuse unsupported parameter kinds
- keep the JSON root schema unchanged
- add compatibility tests for old and new database rows

## Design Recommendation

Implement `add-parameter-type` as a narrow third operation, not as a generalized codemod framework.

That preserves the original trust model:

```text
small supported gesture
-> preview
-> apply
-> test
-> log
-> rollback
```

