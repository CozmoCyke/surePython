# SurePython Phase 3.3 CI Validation Report

## Context

- Branch: `feature/phase-3.3-packaging-multi-os`
- Current HEAD before this diagnostic pass: `d3a1068f2375340e7b2ba1aff60f261a51cbd4ab`
- Main / origin/main: `05d95df34363f85a3f3dea6fea43be1b907360c5`
- Public tag: `v0.16.0-public-preview`
- Local test suite: `308 passed`

## Initial Remote Failure

- Workflow run: `27815247789`
- Workflow name: `ci`
- Commit tested: `d3a1068f2375340e7b2ba1aff60f261a51cbd4ab`
- OS matrix:
  - `windows-latest / Python 3.12`
  - `ubuntu-latest / Python 3.12`
  - `macos-latest / Python 3.12`
- Result: all three jobs failed at `Run tests`
- `Validate contracts` and `Validate release artifacts` were skipped because pytest failed first

## Diagnostic Steps

- Confirmed the release validator was portable only after selecting the venv interpreter by platform.
- Confirmed the existing release checks still passed locally.
- Identified a suspicious test pattern that mutates the global `os.name` module state through `monkeypatch`.
- Reworked the release-path selection into a pure helper, so tests no longer mutate `os.name`.
- Added a `tools` package marker to make local tooling imports explicit and stable.
- Added CI diagnostics in GitHub Actions:
  - explicit diagnostics directory creation
  - JUnit XML output for pytest
  - artifact upload for `.tmp/ci-results`
- Inspected the latest release-validation annotations and found the concrete backend failure:
  - `Backend 'setuptools.build_meta' is not available`
  - the `python -m build --sdist --wheel --no-isolation` step was running without the build backend visible in the CI environment
- Fixed the packaging contract by adding the build-time tools to the editable-install dev extras:
  - `setuptools>=68`
  - `wheel`

## Local Validation

- `python -m pytest tests\test_check_release.py tests\test_packaging_metadata.py tests\test_public_contract.py -q`
  - `13 passed`
- `python -m pytest --collect-only -q`
  - `308 tests collected`
- `python tools/check_release.py`
  - `PASS`
- `build_preview_hash_vectors()` now matches `contracts/fixtures/preview_hash_vectors.json` exactly on the local checkout.

## Current Status

- The suspected global-`os.name` mutation has been removed.
- Pytest diagnostics are now emitted as a downloadable artifact in CI.
- The packaging backend dependency issue has been addressed in `pyproject.toml`.
- The repository remains on the feature branch and `main` is unchanged.
- Status before the next remote run: `READY_FOR_REMOTE_CI_RETRY`

## Open Point

The GitHub Actions public API exposed the release-stage failure clearly, but the next remote run is still needed to confirm the backend fix clears the Windows release validation path end to end.
