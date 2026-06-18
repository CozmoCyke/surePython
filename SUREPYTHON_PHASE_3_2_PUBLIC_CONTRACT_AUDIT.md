# SurePython Phase 3.2 Public Contract Audit

## Reference State

- branch: `feature/phase-3.2-public-contract-freeze`
- baseline commit: `08f68d30d42edda9fcbdc15ffbabffed1ecc8087`
- public preview tag: `v0.15.0-public-preview`
- protocol schema version: `1.0`
- capabilities schema version: `1.0`
- plan schema version: `1.0`

## Public Surface Inventory

### Commands

| Command | Classification | Notes |
| --- | --- | --- |
| `capabilities` | `PUBLIC_STABLE` | Machine-readable capability registry |
| `scan` | `PUBLIC_STABLE` | Symbol scan with text/JSON/CSV output |
| `diff` | `PUBLIC_STABLE` | Git diff viewer |
| `log` | `PUBLIC_STABLE` | SQLite audit log writer |
| `rollback` | `PUBLIC_STABLE` | Explicit rollback by selector |
| `plan preview` | `PUBLIC_EXPERIMENTAL` | Transactional preview |
| `plan apply` | `PUBLIC_EXPERIMENTAL` | Transactional apply |
| `plan rollback` | `PUBLIC_EXPERIMENTAL` | Transactional rollback |
| `plan recover` | `PUBLIC_EXPERIMENTAL` | Transactional recovery |

### Atomic Operations

| Operation | Classification | Notes |
| --- | --- | --- |
| `add-docstring` | `PUBLIC_STABLE` | One skeleton docstring |
| `remove-docstring` | `PUBLIC_EXPERIMENTAL` | Exact docstring removal |
| `add-return-type` | `PUBLIC_EXPERIMENTAL` | Explicit return annotation |
| `remove-return-type` | `PUBLIC_EXPERIMENTAL` | Exact return annotation removal |
| `add-parameter-type` | `PUBLIC_EXPERIMENTAL` | Explicit parameter annotation |
| `remove-parameter-type` | `PUBLIC_EXPERIMENTAL` | Exact parameter annotation removal |
| `add-import` | `PUBLIC_EXPERIMENTAL` | Explicit top-level import insertion |
| `remove-import` | `PUBLIC_EXPERIMENTAL` | Exact top-level import removal |
| `add-decorator` | `PUBLIC_EXPERIMENTAL` | Explicit decorator insertion |
| `remove-decorator` | `PUBLIC_EXPERIMENTAL` | Exact decorator removal |

### Protocol And Storage

- root protocol envelope fields are frozen
- error codes are frozen in `contracts/error_registry_v1.json`
- SQLite remains additive and compatible with historical databases
- the metadata table `surepython_schema_metadata` is additive and does not change existing rows

## Source Of Truth

| Element | Source |
| --- | --- |
| Public contract summary | `contracts/public_contract_v1.json` |
| CLI tree snapshot | `contracts/cli_contract_v1.json` |
| Capability registry | `contracts/capabilities_v1.json` |
| Error registry | `contracts/error_registry_v1.json` |
| Protocol envelope schema | `contracts/protocol_envelope_v1.json` |
| Plan schema | `contracts/plan_schema_v1.json` |
| SQLite schema | `contracts/sqlite_schema_v1.json` |
| Preview hash vectors | `contracts/fixtures/preview_hash_vectors.json` |
| JSON schemas | `contracts/schemas/*.schema.json` |

## Audit Outcome

- all public commands are classified
- all public operations are classified
- all JSON and SQLite surfaces have a frozen snapshot
- no unclassified public element remains in the current freeze scope

