# Installation

SurePython is distributed as a Python package and should install cleanly into a fresh virtual environment.

## Supported Install Paths

- `pip install -e .[dev]` for local development
- `pip install dist\*.whl` for release validation
- `pip install dist\*.tar.gz` for source distribution validation

## Recommended Development Setup

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .[dev]
.\.venv\Scripts\python.exe -m surepython --help
```

## Clean Installation Check

Phase 3.3 validates that a built wheel can be installed into a fresh virtual environment, that `surepython` runs from `site-packages`, and that uninstall removes the importable package.

Do not treat a broken local interpreter, a missing launcher, or a temporary ACL issue as a packaging failure. See `WINDOWS_TROUBLESHOOTING.md` for environment-specific issues.
