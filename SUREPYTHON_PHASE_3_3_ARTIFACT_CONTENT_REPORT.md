# SurePython Phase 3.3 Artifact Content Report

## Expected Wheel Contents

- `surepython/__init__.py`
- `surepython/__main__.py`
- `surepython/cli.py`
- `surepython/package_resources.py`
- `surepython/contracts/*`
- the package metadata files

## Expected Sdist Contents

- `pyproject.toml`
- `README.md`
- `AGENTS.md`
- `docs/*`
- `contracts/*`
- `surepython/*`
- `tests/*`
- `tools/*`

## Forbidden Content

- tests inside the wheel
- repository workflows inside artifacts
- caches
- temporary directories
- SQLite databases

## Verified During Validation

- `python -m build` produced exactly one wheel and one sdist
- `twine check` passed for both artifacts
- the wheel contained the package code and embedded `surepython/contracts/*`
- the sdist contained the source tree, docs, tests, tools, and manifest files required for release review
