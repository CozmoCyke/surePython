# SurePython 1.0.0rc1 Security Review

Status: initial baseline

## Security Properties To Recheck

- refusal before modification
- deterministic preview output
- preview hash enforcement
- transaction lock enforcement
- atomic application
- tests after modification
- SQLite journaling
- exact rollback
- byte restoration
- Git state consistency

## Current RC1 Proof Status

- `refusal before modification`: PASS on the Phase 3.3 baseline
- `deterministic preview output`: PASS on the Phase 3.3 baseline
- `preview hash enforcement`: PASS on the Phase 3.3 baseline
- `transaction lock enforcement`: PASS on the Phase 3.3 baseline
- `atomic application`: PASS on the Phase 3.3 baseline
- `tests after modification`: PASS on the Phase 3.3 baseline
- `SQLite journaling`: PASS on the Phase 3.3 baseline
- `exact rollback`: PASS on the Phase 3.3 baseline
- `byte restoration`: PASS on the Phase 3.3 baseline
- `Git state consistency`: PASS on the Phase 3.3 baseline

The local RC1 validation environment still lacks installed `py` launcher interpreters for 3.10 through 3.14, so the compatibility proof remains `NOT_TESTED` locally for those versions until CI or external runners supply them.

## Scope Guardrails

RC1 must not introduce any new public capability.
Any change that expands the public contract should be treated as out of scope and postponed until after 1.0.0.

## Historical Contract

The frozen public contract currently includes:

- 18 user verbs
- 20 command nodes
- 10 codemods
- 87 public errors
- 2 golden scenarios
- 2 preview hash vectors
- protocol schema 1.0
- capabilities schema 1.0
- plan schema 1.0
- SQLite schema 1.0

## Initial Finding

No new security blocker has been identified yet in this opening audit.
This document will be updated only if a concrete RC blocker or RC-required issue is proven by testing.

## Provisional Classification

- `RC_BLOCKER`: none proven yet
- `RC_REQUIRED`: matrix coverage for 3.10, 3.11, 3.13, and 3.14 remains outstanding
- `ENVIRONMENT_ONLY`: no locally installed `py` launcher interpreters were available to exercise the full matrix
- `ENVIRONMENT_ONLY`: isolated sdist installation in a fresh venv failed on this host because pip could not download build dependencies under socket restrictions

## RC1 Pass 2 Coverage Plan

The following jobs are now defined for remote execution and still need observed results before RC1 can be promoted:

- `build-distributions`
- `source-tests`
- `wheel-clean-install`
- `sdist-clean-install`
- `release-validator`

The `sdist-clean-install` local failure remains `ENVIRONMENT_ONLY` until a connected runner proves the same artifact installs successfully with build isolation intact.

## RC1-COMPAT-001

- `Classification initiale`: `RC_BLOCKER`
- `Cause`: direct `tomllib` usage under Python 3.10 in the packaging metadata test and release validator
- `Impact`: source-tests and release-validator jobs on Python 3.10
- `Runtime wheel/sdist`: unaffected
- `Corrective action`: conditional `tomli` backport in the dev extra and local tool/test imports
- `State`: `FIX_PENDING_REMOTE_VALIDATION`
