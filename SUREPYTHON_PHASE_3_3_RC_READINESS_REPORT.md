# SurePython Phase 3.3 RC Readiness Report

## Collection

- tests collectés: `306`
- fichiers de tests: `18`
- méthode de collection: `python -m pytest --collect-only -q`

## Execution

`FULL_DETERMINISTIC_BATCHED_RUN`

## Readiness Criteria

- clean build from source
- clean install into fresh environments
- clean uninstall
- artifact content validated
- runtime smoke checks validated
- no contract drift

## Status

Phase 3.3 establishes the packaging and validation substrate required before a release candidate.

Current result:

- version surfaces agree at `0.17.0`
- `python -m build --sdist --wheel --no-isolation` passes
- `python -m twine check dist\*` passes
- packaging metadata tests pass
- `tools/check_contracts.py` passes
- the release smoke harness passes
- the release validator passed on the clean source tree with offline bootstrap
- the produced artifacts are exactly:
  - `surepython-0.17.0-py3-none-any.whl`
  - `surepython-0.17.0.tar.gz`

## Final Validation

- `python tools/check_release.py` passed on the clean source tree
- result payload:
  - `ok: true`
  - `version: 0.17.0`
  - `wheel: surepython-0.17.0-py3-none-any.whl`
  - `sdist: surepython-0.17.0.tar.gz`
- `python -m pytest tests/test_packaging_metadata.py -q` passed (`4 passed`)
- `python -m pytest --collect-only -q` found `306` tests in `18` files
- the full suite completed as a deterministic partitioned run in `7` batches
- aggregate result:
  - `passed: 306`
  - `failed: 0`
  - `errors: 0`
  - `skipped: 0`
  - `xfailed: 0`
  - `xpassed: 0`
  - `warnings: 0`
  - total test time: `488.753s`
- the heaviest tests observed were:
  - `tests/test_add_import.py::test_add_import_rollback_restores_exact_bytes[VALUE = 1\\r\\n]` at `10.99s`
  - `tests/test_plans.py::test_plan_apply_rollback_by_last_and_double_rollback_refusal` at `9.59s`
  - `tests/test_plans.py::test_plan_preview_hash_is_deterministic_and_sensitive_to_plan_order` at `8.95s`
  - `tests/test_phase_3_1_transaction_hardening.py::test_plan_fault_injection_recovery_is_idempotent` at `8.35s`
  - `tests/test_plans.py::test_plan_apply_and_rollback_by_id_restores_bytes_and_logs` at `7.91s`

## Readiness Conclusion

`READY_FOR_PHASE_3_3_PRE_MERGE_REVIEW`

## Limits

- Linux CI: not yet proven in this session
- macOS CI: not yet proven in this session
- other Python versions: not yet proven in this session
- preview hash cross-OS real run: not yet proven in this session
- lock cross-OS real run: not yet proven in this session
- SQLite cross-OS real run: not yet proven in this session
