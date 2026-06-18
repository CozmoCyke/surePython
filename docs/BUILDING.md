# Building

SurePython builds standard Python distribution artifacts.

## Build Commands

```powershell
.\.venv\Scripts\python.exe -m pip install -e .[dev]
.\.venv\Scripts\python.exe -m build --no-isolation
.\.venv\Scripts\python.exe -m twine check dist\*
```

## What A Correct Build Produces

- exactly one wheel
- exactly one sdist
- no tests, caches, or GitHub workflows inside the artifacts
- embedded contract resources under `surepython/contracts/`

## Release Validator

`tools/check_release.py` performs the build, inspects the artifact contents, installs both artifacts into fresh environments, runs runtime smoke tests, and confirms uninstall removal.

Use the validator from a clean worktree before tagging a release candidate.
