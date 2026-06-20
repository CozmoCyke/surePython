# SurePython 1.0.0rc1 Compatibility Matrix

Status: initial baseline

## Declared Support

`requires-python = ">=3.10"`

The RC1 validation matrix should cover the announced range:

- Python 3.10
- Python 3.11
- Python 3.12
- Python 3.13
- Python 3.14

## Platform Targets

- Windows
- Ubuntu/Linux
- macOS

## Current Verified Baseline

Phase 3.3 proved the distribution path on:

- Windows 11 with Python 3.12
- Linux with Python 3.12
- macOS with Python 3.12

Current local environment note:

- `py` launcher reports no installed Pythons
- the repository `.venv` is still the only immediately available interpreter for local smoke work

## RC1 Pass 2 Target Jobs

The RC1 pass 2 workflow now defines the following jobs for remote validation:

| Job | Scope | Current status | Evidence expected |
| --- | --- | --- | --- |
| `build-distributions` | Ubuntu / Python 3.12 | NOT_TESTED | wheel, sdist, proof JSON, twine check |
| `source-tests` | Ubuntu / Python 3.10-3.14; Windows / Python 3.10, 3.12, 3.14; macOS / Python 3.10, 3.12, 3.14 | NOT_TESTED | editable install, pytest, contracts, compileall |
| `wheel-clean-install` | Ubuntu / Python 3.10-3.14; Windows / Python 3.12; macOS / Python 3.12 | NOT_TESTED | install from the shared wheel artifact, import from site-packages, smoke commands |
| `sdist-clean-install` | Ubuntu / Python 3.10-3.14; Windows / Python 3.12; macOS / Python 3.12 | NOT_TESTED | install from the shared sdist artifact, import from site-packages, smoke commands |
| `release-validator` | Ubuntu / Python 3.10, 3.12, 3.14; Windows / Python 3.12; macOS / Python 3.12 | NOT_TESTED | full release chain, build, install, smoke, rollback |

## RC1 Validation Gap

The following still need direct RC1 verification before the release candidate can be declared ready:

- Python 3.10 clean install and smoke tests
- Python 3.11 clean install and smoke tests
- Python 3.13 clean install and smoke tests
- Python 3.14 clean install and smoke tests
- wheel installation in a fresh virtual environment
- sdist installation in a fresh virtual environment
- uninstall cleanup from both artifact types
- remote CI confirmation for all RC1 pass 2 jobs

## Matrix Status

| OS | Python | editable install | pytest | contracts | wheel | sdist | release validator | result | proof |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Windows | 3.12 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | Phase 3.3 release evidence |
| Windows | 3.10 | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | No local interpreter available |
| Windows | 3.11 | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | No local interpreter available |
| Windows | 3.13 | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | No local interpreter available |
| Windows | 3.14 | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | No local interpreter available |
| Ubuntu | 3.12 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | Phase 3.3 release evidence |
| Ubuntu | 3.10 | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | No local interpreter available |
| Ubuntu | 3.11 | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | No local interpreter available |
| Ubuntu | 3.13 | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | No local interpreter available |
| Ubuntu | 3.14 | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | No local interpreter available |
| macOS | 3.12 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | Phase 3.3 release evidence |
| macOS | 3.10 | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | No local interpreter available |
| macOS | 3.11 | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | No local interpreter available |
| macOS | 3.13 | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | No local interpreter available |
| macOS | 3.14 | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | No local interpreter available |

## First RC1 Local Validation Pass

| OS | Python | editable install | pytest | contracts | wheel | sdist | release validator | result | proof |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Windows | 3.12.13 (`.venv`) | PASS | PASS (`311 passed`) | PASS | PASS | FAIL | FAIL | `ENVIRONMENT_ONLY` for isolated sdist build dependencies | `tools/check_release.py` failed because pip could not fetch `setuptools>=68` in a fresh venv under local network/socket restrictions |
| Windows | 3.12.13 (`.venv`) | PASS | PASS (`14 passed`) | PASS | N/A | N/A | N/A | Targeted contract and packaging tests | `tests/test_check_release.py`, `tests/test_packaging_metadata.py`, `tests/test_public_contract.py` |

## Interpretive Note

This first pass does **not** prove RC1 readiness. It only proves that the current codebase still passes the full test suite on the repository `.venv` and that the release validator currently encounters an environment-only obstacle when it tries to install the sdist into a fresh venv without network access.

## Matrix Rule

If a version or platform is part of the release promise, it must be validated directly or explicitly removed from the promise before RC1 is tagged.
