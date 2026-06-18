# SurePython Phase 3.2 Contract Matrix

| Public element | Source of truth | Snapshot | Test | Documentation |
| --- | --- | --- | --- | --- |
| CLI tree | `surepython/cli.py` | `contracts/cli_contract_v1.json` | `tests/test_public_contract.py` | `README.md`, `docs/PUBLIC_API.md` |
| Capability registry | `surepython/capabilities.py` | `contracts/capabilities_v1.json` | `tests/test_capabilities.py`, `tests/test_public_contract.py` | `README.md`, `docs/CODEX_INTEGRATION.md` |
| Error registry | `surepython/protocol.py` | `contracts/error_registry_v1.json` | `tests/test_public_contract.py` | `docs/ERROR_CODES.md` |
| Protocol envelope | `surepython/protocol.py` | `contracts/protocol_envelope_v1.json` | `tests/test_protocol_json.py`, `tests/test_public_contract.py` | `docs/PROTOCOL_JSON.md` |
| Plan schema | `surepython/plans.py` | `contracts/plan_schema_v1.json` | `tests/test_plans.py`, `tests/test_public_contract.py` | `docs/PLAN_SCHEMA_V1.md`, `docs/TRANSACTIONAL_PLANS.md` |
| SQLite schema | `surepython/datasette_log.py` | `contracts/sqlite_schema_v1.json` | `tests/test_rollback.py`, `tests/test_public_contract.py` | `docs/SELF_HOSTING.md`, `docs/WINDOWS_TROUBLESHOOTING.md` |
| Preview hash vectors | `surepython/plans.py` | `contracts/fixtures/preview_hash_vectors.json` | `tests/test_public_contract.py` | `docs/PLAN_SCHEMA_V1.md`, `docs/TRANSACTIONAL_PLANS.md` |
| Compatibility policy | docs and contract snapshots | `contracts/public_contract_v1.json` | `tools/check_contracts.py` | `docs/COMPATIBILITY_POLICY.md` |

## Coverage Note

Every public row above has at least one test and one documentation path.
The contract matrix itself is part of the freeze so future changes can be reviewed against the same reference.

