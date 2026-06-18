# Versioning Policy

SurePython tracks several versions independently.

## Package Version

The package version is the release number of the installed tool.

## Contract Versions

The public contract uses explicit schema versions:

- `protocol_schema_version`
- `capabilities_schema_version`
- `plan_schema_version`

## Internal Persistence

SQLite is a persistent internal format with additive migrations.
It is not a promise that raw SQL is a public API.

## Rule

A package release may advance without changing the contract versions.
A contract version change means the machine-readable shape has changed and must be tested.

## Release Artifacts

The package version also identifies the wheel and sdist produced from the repository root.
Phase 3.3 requires those artifacts to install cleanly into fresh environments and to preserve the frozen public contracts.

