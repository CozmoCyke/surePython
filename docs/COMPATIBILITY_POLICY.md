# Compatibility Policy

SurePython Phase 3.2 freezes the public contract at version `1.0` for:

- `protocol_schema_version`
- `capabilities_schema_version`
- `plan_schema_version`

The public contract is captured in `contracts/public_contract_v1.json` and validated by `tools/check_contracts.py`.

## Compatible Change

A change is compatible when it:

- adds a new optional field
- adds a new optional capability
- adds a new public error code for a real code path
- adds a new documented snapshot without changing existing meanings

## Breaking Change

A change is breaking when it:

- removes or renames a public field
- changes the type or meaning of a field
- makes a previously optional item required
- changes canonicalization rules
- changes the plan hash contract
- changes the meaning of an existing error code

## Rule

If a change cannot be represented as additive and backward compatible, it needs:

1. a new versioned contract
2. a migration plan
3. tests
4. a breaking-change note

