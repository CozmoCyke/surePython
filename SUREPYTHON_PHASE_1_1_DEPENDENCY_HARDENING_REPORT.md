# SurePython Phase 1.1 Dependency Hardening Report

## Objective

Replace the temporary local shims used in v0.1 with official dependencies, without changing the feature set.

## Changes made

- Added official dependency declarations for `libcst` and `pytest` in `pyproject.toml`
- Added `sitecustomize.py` to place the local vendor tree on `sys.path`
- Removed the root-level `libcst.py` shim
- Removed the root-level `pytest.py` shim
- Reworked `surepython/codemods.py` to use real LibCST parsing and transformation APIs
- Copied the downloaded wheels into `.vendor3`, which has readable permissions for the runtime Python process
- Pointed the runtime `sitecustomize.py` at `.vendor3`

## Validation

Validated commands:

- `python -m surepython scan tests\fixtures`
- `python -m surepython diff`
- `python -m pytest`

## Notes

The first wheel tree ended up with ACLs that Python could not stat, even though `cmd` could list the files. Copying that tree into `.vendor3` produced a readable vendor directory, which allowed the real packages to import.

If the environment regresses again, the failure should be investigated at interpreter startup or path/ACL level, not by reintroducing behavioral shims.
