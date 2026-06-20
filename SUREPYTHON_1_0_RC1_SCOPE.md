# SurePython 1.0.0rc1 Scope

Status: `RC1_STABILIZATION_IN_PROGRESS`

## Baseline

- Branch: `release/1.0.0-rc1`
- Base commit: `a6e5570c689767ae32486b2c7b77d90c293828d6`
- Public tag: `v0.17.0-public-preview`
- Package version at start of RC1: `0.17.0`
- Current public contract versions:
  - `protocol_schema_version = 1.0`
  - `capabilities_schema_version = 1.0`
  - `plan_schema_version = 1.0`
  - `sqlite_schema_v1`

## Allowed Work

- Bug fixes
- Portability fixes
- Packaging fixes
- Security fixes
- Transaction and rollback fixes
- Contract consistency fixes
- Test and diagnostics improvements
- Documentation clarifications that do not change behavior
- Adaptations needed for officially supported Python versions

## Forbidden Work

- New codemods
- New public commands
- New public arguments that are not strictly necessary to fix a blocker
- New plan formats
- New protocol versions
- New public error codes unless a blocker proves they are required
- Opportunistic architecture changes
- Datasette plugins
- GUI work
- Additional agent integrations
- Premature PyPI publication

## RC1 Goal

Demonstrate that the current SurePython core is:

- stable
- portable
- installable from wheel and sdist
- safe under the frozen public contract
- ready for release-candidate validation

## Initial Assessment

No source changes have been made for RC1 yet.
The current repository state is the Phase 3.3 public preview baseline.
The next step is to validate the frozen contract against fresh installs and supported environments without expanding the public surface.

## Local Environment Note

- The Windows `py` launcher reports no installed interpreters on this machine.
- RC1 validation therefore starts from the repository `.venv` only, until CI or another host provides Python 3.10, 3.11, 3.13, and 3.14.
- That limitation is environment-only; it does not change the RC1 scope.
