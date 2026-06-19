# SurePython Phase 3.3 Pre-Merge Review

## State

- branch: `feature/phase-3.3-packaging-multi-os`
- initial HEAD: `e12f4ee2845ded75e041ea35011f182242ee3640`
- latest local commit: `e12f4ee2845ded75e041ea35011f182242ee3640`
- commit subject: `Record complete Phase 3.3 test evidence`
- `main`: `05d95df34363f85a3f3dea6fea43be1b907360c5`
- `origin/main`: `05d95df34363f85a3f3dea6fea43be1b907360c5`
- public tag: `v0.16.0-public-preview`
- peeled public tag: `05d95df34363f85a3f3dea6fea43be1b907360c5`
- worktree: clean
- package version: `0.17.0`
- normative version source: `pyproject.toml`
- artifacts:
  - `surepython-0.17.0-py3-none-any.whl`
  - `surepython-0.17.0.tar.gz`

## Delta Inspected

The Phase 3.3 delta is limited to packaging, release validation, documentation, contracts, CI workflows, and tests.

Changed files include:

- `pyproject.toml`
- `surepython/__init__.py`
- `surepython/package_resources.py`
- `surepython/contracts/*`
- `tools/check_release.py`
- `tests/test_packaging_metadata.py`
- `tests/test_public_contract.py`
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- documentation and reports under `docs/` and `SUREPYTHON_PHASE_3_3_*.md`

No new user command, codemod, plan schema, or public JSON contract drift was introduced.

## Version And Build

- `version = 0.17.0`
- source of truth: `pyproject.toml`
- `importlib.metadata.version("surepython")` matches `surepython.__version__`
- backend: `setuptools.build_meta`
- `Requires-Python = >=3.10`
- runtime dependency: `libcst>=1.8`
- development extras: `build>=1.2`, `pytest>=9.0`, `twine>=6.0`

The release validator passed on the clean source tree:

- `python tools/check_release.py`
- result:
  - `ok: true`
  - `version: 0.17.0`
  - `wheel: surepython-0.17.0-py3-none-any.whl`
  - `sdist: surepython-0.17.0.tar.gz`

`twine check dist\*` passed.

## Complete Test Evidence

### Collection

- collected tests: `306`
- test files: `18`
- collection method: `python -m pytest --collect-only -q`

### Execution

- execution mode: `FULL_DETERMINISTIC_BATCHED_RUN`
- batches: `7`
- passed: `306`
- failed: `0`
- errors: `0`
- skipped: `0`
- xfailed: `0`
- xpassed: `0`
- warnings: `0`
- cumulative test time: `488.753s`

The heaviest observed tests were:

- `tests/test_add_import.py::test_add_import_rollback_restores_exact_bytes[VALUE = 1\r\n]` at `10.99s`
- `tests/test_plans.py::test_plan_apply_rollback_by_last_and_double_rollback_refusal` at `9.59s`
- `tests/test_plans.py::test_plan_preview_hash_is_deterministic_and_sensitive_to_plan_order` at `8.95s`
- `tests/test_phase_3_1_transaction_hardening.py::test_plan_fault_injection_recovery_is_idempotent` at `8.35s`
- `tests/test_plans.py::test_plan_apply_and_rollback_by_id_restores_bytes_and_logs` at `7.91s`

### Targeted Tests

- packaging metadata: `4 passed`
- public contract: `7 passed`

## Artifact Review

The wheel and sdist were rebuilt and checked successfully.

The packaging validator proved:

- runtime package files are included
- contract resources are included
- distribution artifacts do not contain `.git`, `.tmp`, build caches, local databases, or other forbidden paths
- the wheel imports from `site-packages` in a clean environment
- the sdist can be installed and executed outside the checkout
- `python -m surepython` and the `surepython` entry point both work

## Smoke Review

Local smoke proof is established for:

- `scan`
- `capabilities --format json`
- codemod dry-runs
- codemod application with SQLite logging
- `rollback --last`
- `rollback --id`
- `plan preview`
- `plan apply`
- `plan rollback`
- `plan recover`

## Workflows

Workflows present:

- [`.github/workflows/ci.yml`](C:\dev\datasette-lab\surePython\.github\workflows\ci.yml)
- [`.github/workflows/release.yml`](C:\dev\datasette-lab\surePython\.github\workflows\release.yml)

The CI workflow targets:

- `windows-latest`
- `ubuntu-latest`
- `macos-latest`
- Python `3.12`

The release workflow is manual and runs on `windows-latest` with Python `3.12`.

## Defects Found

No blocking packaging or contract defect was found during this local review.

## Risks Remaining

- Linux CI has not yet been observed in this session.
- macOS CI has not yet been observed in this session.
- other Python versions have not yet been observed in this session.
- cross-OS preview hash and SQLite behavior still require remote CI evidence.
- `gh auth status` reports no logged-in GitHub host in this environment, so remote runs could not be queried.

## Recommendation

Local recommendation: `READY_FOR_REMOTE_CI`

Remote CI status: `PENDING_REMOTE_CI`

The branch was not pushed from this session because the GitHub CLI is not authenticated here and the remote runs could not be inspected.
