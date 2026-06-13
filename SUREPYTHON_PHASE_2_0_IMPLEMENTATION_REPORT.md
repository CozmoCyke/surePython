# SurePython Phase 2.0 Implementation Report

## Objective

Phase 2.0 proves that SurePython can host more than one controlled operation without becoming a general-purpose coding engine.

The phase adds:

- a minimal machine-readable capabilities registry
- a `capabilities` CLI command
- one new codemod: `add-return-type`
- rollback support for the new operation
- tests for extensibility, logging, rollback, and Windows byte preservation

No other codemod was added.

## Architecture Retained

The implementation deliberately avoids a large plugin framework.

New and changed components:

- `surepython/capabilities.py` stores the declarative operation registry.
- `surepython/cli.py` exposes `capabilities` and `add-return-type`.
- `surepython/codemods.py` adds `add_return_type()` while reusing Git checks, target resolution, pytest execution, diffing, and SQLite state writing.
- `surepython/datasette_log.py` can now read the latest rollback-compatible operation across supported operation names.
- `surepython/rollback.py` dispatches rollback by operation type.
- `surepython/scanner.py` reads Python source with `utf-8-sig` for analysis so BOM files can be scanned safely.
- `surepython/__main__.py` now propagates `main()` through `SystemExit`, so `python -m surepython` returns CLI error codes correctly.

The SQLite schema is unchanged.

## Capabilities Command

Human-readable:

```powershell
python -m surepython capabilities
```

Machine-readable:

```powershell
python -m surepython capabilities --format json
```

The JSON shape is:

```json
{
  "operations": [
    {
      "name": "add-docstring",
      "description": "...",
      "targets": ["function", "method"],
      "required_arguments": ["file", "function"],
      "supports_dry_run": true,
      "supports_tests": true,
      "supports_logging": true,
      "supports_rollback": true,
      "status": "stable"
    }
  ]
}
```

The registry lists only operations currently implemented.

## Add-Return-Type Contract

Command:

```powershell
python -m surepython add-return-type <file.py> --function <symbol> --annotation "<annotation>" [--dry-run] [--test] [--db <path>]
```

Behavior:

- targets one function or method
- supports qualified `Class.method`
- receives the annotation explicitly
- validates annotation syntax
- refuses existing return annotations
- modifies only the return annotation
- does not infer types
- does not add imports
- does not touch parameters
- does not rewrite function bodies
- supports dry-run
- supports pytest after a real edit
- supports SQLite logging
- supports explicit rollback

## Rollback

Rollback now reads the latest compatible logged operation:

- `add-docstring`
- `add-return-type`

It dispatches the inverse transform by operation type:

- `add-docstring` removes the SurePython skeleton docstring
- `add-return-type` removes the return annotation

The hash contract remains unchanged:

- current file hash must match `after_sha256`
- restored bytes must match `before_sha256`
- rollback refuses rather than approximating

`legacy/unverifiable` records remain refused without writing.

## SQLite Compatibility

No schema migration was introduced.

The existing `operation` field distinguishes:

- `add-docstring`
- `add-return-type`
- `rollback`

Existing `add-docstring` records remain compatible.

## Tests Added

Coverage includes:

- capabilities JSON
- capabilities text
- simple function return annotation
- qualified method return annotation
- homonymous methods in two classes
- async function
- `str`
- `list[str]`
- `User | None`
- existing annotation refusal
- invalid annotation refusal
- missing target refusal
- ambiguous target refusal
- dry-run without writing
- pytest success reporting
- SQLite logging
- rollback real byte-exact
- LF files
- CRLF files
- UTF-8 BOM files
- hash mismatch refusal without writing
- non-regression of `add-docstring`
- `python -m surepython` exit-code propagation

Current test count:

```text
60 passed
```

## CRLF Smoke Result

A real temporary Git repository validated:

```text
CRLF file
-> add-return-type --test --db
-> commit
-> rollback --dry-run
-> rollback
-> byte-identical restoration
-> SQLite rollback/rolled_back
```

Hashes:

```text
before_sha256    = b0a2a0801f2b7f1ae84257cdc65fb5a7811dc4a5db008946fcc90c5318bd322f
after_add_sha256 = d469499a46f5d0f6ece8410c9d54a2c7740a15c50b9aea2a75eb47ed94d9a6ad
restored_sha256  = b0a2a0801f2b7f1ae84257cdc65fb5a7811dc4a5db008946fcc90c5318bd322f
bytes_equal      = True
```

SQLite rows confirmed:

- `add-return-type / tested / pytest_status = passed`
- `rollback / rolled_back`

## Known Limits

SurePython still does not:

- infer return types
- replace existing annotations
- add imports
- guarantee pytest success for annotations that are syntactically valid but not runtime-resolvable in the target project
- modify parameters
- operate on multiple functions
- roll back multiple operations
- roll back by date range
- restore from Git blobs
- run arbitrary codemods

## Validation Commands

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp .\.tmp\pytest_phase_2_0
.\.venv\Scripts\python.exe -m surepython capabilities --format json
.\.venv\Scripts\python.exe -m surepython scan tests\fixtures --format json
.\.venv\Scripts\python.exe -m surepython diff
git diff --check
git status --short
```

## Phase Principle

Codex can propose the annotation.

SurePython only verifies that the requested operation is declared, narrow, syntactically valid, logged, testable, and reversible.
