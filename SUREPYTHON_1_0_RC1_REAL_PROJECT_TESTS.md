# SurePython 1.0.0rc1 Real Project Tests

Status: planned baseline

## Test Project Shapes

RC1 should exercise SurePython on representative projects:

- a small standalone Python module
- a classic Python package
- a project with `pyproject.toml`
- a project with pytest tests
- a multi-module project
- a project using different typing styles

## Test Goals

- install SurePython from a built wheel
- install SurePython from a built sdist
- run the `surepython` console script
- run `python -m surepython`
- validate dry-run, apply, journal, and rollback behavior
- confirm the installed package does not depend on the checkout

## Current State

No new real-project RC1 test corpus has been executed yet.
Phase 3.3 already validated the packaged distribution path on fresh virtual environments, but RC1 needs the broader project coverage described above.

