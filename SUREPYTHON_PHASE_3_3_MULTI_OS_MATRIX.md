# SurePython Phase 3.3 Multi-OS Matrix

## Planned Validation Matrix

- Windows 11, Python 3.12
- Ubuntu latest, Python 3.12
- macOS latest, Python 3.12

## Coverage

- clean install
- runtime import
- CLI invocation
- artifact inspection
- uninstall check

## Notes

The matrix documents the supported release validation surface. It does not expand the public contract.

## Current State

- Windows packaging validation was executed locally in this workspace
- the CI workflow now lists Windows, Linux, and macOS jobs at Python 3.12
- the release validator is designed to run from a clean tree on every supported platform
