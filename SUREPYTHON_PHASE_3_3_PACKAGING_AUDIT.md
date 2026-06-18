# SurePython Phase 3.3 Packaging Audit

Phase 3.3 extends SurePython from a contract-frozen product into a cleanly packaged distribution.

## Goals

- prove wheel and sdist builds from a clean tree
- prove clean installation into fresh virtual environments
- prove uninstall removes the package cleanly
- keep packaged artifacts free of tests, caches, and workflow files
- keep the public CLI and contract snapshots unchanged

## Initial Findings

- package metadata is stored in `pyproject.toml`
- runtime package version is derived from package metadata with a fallback to `pyproject.toml`
- package resources are read from installed package data
- contract files are bundled into the package for release validation
- release validation can be automated with `tools/check_release.py`

## Audit Notes

- packaging must remain additive
- release verification must not expand the supported edit set
- wheel and sdist contents should remain predictable across platforms
- the artifact validator should report cleanly when build tools are missing
- the repository uses local bootstrap infrastructure (`.vendor3`) for offline validation in this workspace
- setuptools package discovery must be constrained to `surepython*` because the repository also contains a top-level `contracts/` directory
