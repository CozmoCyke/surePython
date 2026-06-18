# Public API

SurePython exposes a narrow public surface.

## Public Commands

- `capabilities`
- `scan`
- `diff`
- `log`
- `rollback`
- `plan preview`
- `plan apply`
- `plan rollback`
- `plan recover`
- `add-docstring`
- `remove-docstring`
- `add-return-type`
- `remove-return-type`
- `add-parameter-type`
- `remove-parameter-type`
- `add-import`
- `remove-import`
- `add-decorator`
- `remove-decorator`

## Public Contracts

- `contracts/public_contract_v1.json`
- `contracts/cli_contract_v1.json`
- `contracts/capabilities_v1.json`
- `contracts/error_registry_v1.json`
- `contracts/protocol_envelope_v1.json`
- `contracts/plan_schema_v1.json`
- `contracts/sqlite_schema_v1.json`
- `contracts/fixtures/preview_hash_vectors.json`

## Packaging And Release Helpers

- `tools/check_release.py` validates the built distribution artifacts and clean-install behavior.
- `python -m build` and `python -m twine check` are release-time checks rather than runtime API surface.

## API Boundary

The stable public API is the CLI plus its JSON contract.
Python modules are internal implementation details unless a document explicitly says otherwise.
Packaging helpers document release validation, but they do not expand the runtime public API.

