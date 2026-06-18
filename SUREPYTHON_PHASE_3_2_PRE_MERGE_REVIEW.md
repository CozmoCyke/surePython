# SurePython Phase 3.2 Pre-Merge Review

## Summary

- Branch: `feature/phase-3.2-public-contract-freeze`
- Implementation commit: `3832e67a41ee84181e78a70a3198d368cdf05af2`
- Commit subject: `Freeze the SurePython 1.0 public contract`
- `main` / `origin/main`: `08f68d30d42edda9fcbdc15ffbabffed1ecc8087`
- Public preview tag: `v0.15.0-public-preview` -> `08f68d30d42edda9fcbdc15ffbabffed1ecc8087`
- Worktree: clean
- Push/tag activity: none

## Verdict

Phase 3.2 is ready for merge from a contract-frozen perspective.

I did not find a blocking mismatch between the public CLI, the protocol envelope, the capabilities registry, the plan schema, the SQLite contract, the normative documentation, and the frozen snapshots under `contracts/`.

## Source of Truth

The normative public contract is the frozen snapshot set under `contracts/`.

The live Python code in `surepython/public_contract.py` is the generator/reference implementation used to derive and validate the snapshots, and `tools/check_contracts.py` is the drift detector that compares the code, snapshots, schemas, corpus, and normative docs.

So the operational model is:

`public code -> frozen snapshots -> validator`

This is a single controlled pipeline, not multiple independently editable public contracts.

## Delta Reviewed

Reviewed files include:

- `AGENTS.md`
- `README.md`
- `docs/AGENTS_TEMPLATE.md`
- `docs/CODEX_INTEGRATION.md`
- `docs/PLAN_SCHEMA_V1.md`
- `docs/PROTOCOL_JSON.md`
- `docs/SELF_HOSTING.md`
- `docs/TRANSACTIONAL_PLANS.md`
- `docs/TUTORIAL_FR.md`
- `docs/WINDOWS_TROUBLESHOOTING.md`
- `surepython/datasette_log.py`
- `surepython/public_contract.py`
- `tests/test_public_contract.py`
- `tools/check_contracts.py`
- `contracts/*`
- `docs/COMPATIBILITY_POLICY.md`
- `docs/DEPRECATION_POLICY.md`
- `docs/ERROR_CODES.md`
- `docs/PUBLIC_API.md`
- `docs/VERSIONING_POLICY.md`
- `SUREPYTHON_PHASE_3_2_PUBLIC_CONTRACT_AUDIT.md`
- `SUREPYTHON_PHASE_3_2_BREAKING_CHANGE_AUDIT.md`
- `SUREPYTHON_PHASE_3_2_IMPLEMENTATION_REPORT.md`
- `SUREPYTHON_PHASE_3_2_SELF_HOSTING_LOG.md`
- `SUREPYTHON_PHASE_3_2_CONTRACT_MATRIX.md`

No new codemod, network API, server, MCP surface, or destructive SQLite migration was introduced.

## CLI Inventory

The frozen argparse tree exposes:

- 16 top-level public parser entries
- 18 user-visible verbs when counting `plan` subcommands separately
- 10 codemods
- 2 top-level command families in the capabilities registry: `rollback` and `plan`

Public verbs checked against the snapshot:

- `capabilities`
- `scan`
- `diff`
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
- `rollback`
- `plan preview`
- `plan apply`
- `plan rollback`
- `plan recover`

The tree and the snapshot agree on required/optional arguments, defaults, choices, and selector structure.

## JSON Envelope

The protocol root remains:

- `protocol_schema_version = "1.0"`
- `capabilities_schema_version = "1.0"`

The public JSON contract remains stable for:

- success
- refusal
- tests failed
- rollback
- plan preview/apply/rollback/recover

I found no accidental traceback leakage, no extra stdout pollution, and no unstable root fields in the frozen snapshots.

## Status and Error Registry

The public error registry is coherent with the code and the contract snapshots.

Key counts:

- stable public error codes: `87`
- JSON schema files: `6`

The review did not uncover:

- a code produced but missing from the registry
- a declared code that is never reachable
- a documented code misspelled relative to the implementation
- a public exposure of test-only/internal error names

## Capabilities

The frozen capabilities registry remains aligned with the implementation.

Counts:

- codemods: `10`
- public command families in capabilities: `2`

No unstable fields were found in the frozen capabilities payload.

## Plan Schema

The frozen plan contract and the runtime validator remain aligned.

The review did not find:

- an accidental new plan type
- a silent change to plan step semantics
- a mismatch between the plan schema snapshot and the runtime validator
- a destructive SQLite migration associated with the contract freeze

## Preview Hash

The preview hash vectors are present and stable.

Counts:

- preview hash vectors: `2`

The vectors are derived from portable inputs and do not encode machine-specific values as part of the frozen contract.

## Path Canonicalization

The frozen contract does not depend on local machine paths, hostnames, or user-specific data.

The validator and snapshots use canonical project-relative shapes, and the review did not find a Windows-only dependency in the public contract surface.

## SQLite Compatibility

The review found an additive schema metadata table in `surepython/datasette_log.py`.

This is compatible with the freeze goal because:

- it is additive
- it keeps prior records readable
- it does not rename or drop historical columns
- it gives the contract a stable schema fingerprint

Observed compatibility posture:

- versioned SQLite fixture files in the repository: `0`
- historical compatibility is exercised through runtime tests and generated temporary databases rather than checked-in `.sqlite` assets

## Golden Corpus

Counts:

- golden scenarios: `2`

The corpus is parseable and is used as a contract validation artifact rather than a feature surface.

## Documentation Normative Set

The normative docs were checked for parseable JSON blocks and alignment with the snapshot set.

I did not find contradictions between:

- `README.md`
- `docs/TUTORIAL_FR.md`
- `docs/CODEX_INTEGRATION.md`
- `docs/AGENTS_TEMPLATE.md`
- `docs/PUBLIC_API.md`
- `docs/ERROR_CODES.md`
- `docs/PROTOCOL_JSON.md`
- `docs/PLAN_SCHEMA_V1.md`
- `docs/TRANSACTIONAL_PLANS.md`
- `docs/SELF_HOSTING.md`
- `docs/WINDOWS_TROUBLESHOOTING.md`

## Sensitive Data Check

The public contract snapshots avoid embedding unstable environment-specific values such as:

- real user home paths
- hostnames
- PIDs
- secrets

## Validation Performed

Successful checks:

- `python tools/check_contracts.py`
- `python -m pytest tests/test_public_contract.py -q`
- `python -m surepython capabilities --format json`
- `python -m surepython scan surepython --format json`
- `python -m surepython diff`
- `git diff --check`

Test inventory:

- total collected tests: `302`
- contract tests in `tests/test_public_contract.py`: `7`

## Findings

No blocking defect was found during this review.

The contract freeze is internally consistent, drift-checked, and compatible with the historical behavior covered by the test suite.

## Recommendation

Ready for transfer.

