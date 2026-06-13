# SurePython

SurePython is a safety layer between AI-generated Python changes and real code.

Codex may propose, but SurePython verifies, limits, applies, shows the diff, runs tests, logs the operation, and can roll back the supported change when the log proves it is safe.

The name carries two meanings:

- safe Python
- Python you can be sure about

## What SurePython Is Today

SurePython is a local CLI for controlled Python micro-modifications.

It is not a general refactoring engine. It currently supports one deliberately small edit:

```python
"""TODO: Document this function."""
```

SurePython currently supports two deliberately narrow operations:

- add one skeleton docstring to one targeted Python function or method, only when the target has no existing docstring
- add one explicit return annotation to one targeted Python function or method, only when the target has no existing return annotation

The working pipeline is:

```text
capabilities -> scan -> dry-run -> supported operation -> pytest -> SQLite log -> rollback
```

This small scope is intentional. SurePython is designed to refuse when it cannot prove the operation.

## Trust Model

SurePython separates reasoning from execution:

- Codex can explore, explain, and propose broad changes.
- SurePython executes only the transformations it knows how to locate, verify, apply, test, log, and restore.
- Git shows the scar.
- Pytest checks the vital signs.
- SQLite and Datasette keep the medical record.

A refusal is not a failure of the tool. A refusal protects the project.

## Commands

```powershell
python -m surepython capabilities
python -m surepython capabilities --format json
```

`capabilities --format json` is the machine-readable contract for Codex and other agents. It lists only operations that SurePython actually supports.

```powershell
python -m surepython scan tests\fixtures
python -m surepython scan tests\fixtures --format text
python -m surepython scan tests\fixtures --format json
python -m surepython scan tests\fixtures --format csv
```

`scan` lists Python symbols with these fields:

- `file`
- `type`
- `name`
- `qualified_name`
- `line_start`
- `line_end`
- `has_docstring`

```powershell
python -m surepython add-docstring tests\fixtures\sample_module.py --function sample_function --dry-run
python -m surepython add-docstring tests\fixtures\sample_module.py --function SampleClass.sample_method --dry-run
python -m surepython add-docstring tests\fixtures\sample_module.py --function SampleClass.sample_method --test --db .\surepython_lab.db
python -m surepython add-docstring tests\fixtures\sample_module.py --function SampleClass.sample_method --dry-run --format json
```

`add-docstring` accepts:

- `--function NAME`
- `--function Class.method`
- `--dry-run`
- `--test`
- `--test-command "<command>"`
- `--db <sqlite-path>`

```powershell
python -m surepython add-return-type src\service.py --function UserService.load_user --annotation "User | None" --dry-run
python -m surepython add-return-type src\service.py --function UserService.load_user --annotation "User | None" --test --db .\surepython_lab.db
python -m surepython add-return-type src\service.py --function UserService.load_user --annotation "User | None" --dry-run --format json
```

`add-return-type` accepts:

- `--function NAME`
- `--function Class.method`
- `--annotation "<type expression>"`
- `--dry-run`
- `--test`
- `--test-command "<command>"`
- `--db <sqlite-path>`

SurePython never infers the annotation. Codex or a human proposes it; SurePython validates and inserts it exactly.

`add-return-type` validates syntax, not semantic availability. If an annotation references a name that the project cannot resolve at runtime, `--test` should expose that failure.

```powershell
python -m surepython diff
```

`diff` prints `git diff --stat` and `git diff`.

```powershell
python -m surepython log --db .\surepython_lab.db
```

`log` manually replays the last SurePython operation state into SQLite. It remains available even though real operations with `--db` can log automatically.

```powershell
python -m surepython rollback --last --db .\surepython_lab.db --dry-run
python -m surepython rollback --last --db .\surepython_lab.db
python -m surepython rollback --id 42 --db .\surepython_lab.db
python -m surepython rollback --last --db .\surepython_lab.db --format json
python -m surepython rollback --id 42 --db .\surepython_lab.db --format json
```

`rollback` is explicit, database-backed, and limited to compatible logged `add-docstring` or `add-return-type` operations. It supports either `--last` or `--id <operation_id>`, but never both.

## Agent Protocol

SurePython phase 2.1 adds a stable JSON protocol for agents.

- request `--format json` explicitly
- parse `protocol_schema_version`
- use `capabilities --format json` before selecting an operation
- expect `operation_id` only for real SQLite writes
- expect dry-runs to return `operation_id: null`
- expect refusal codes such as `ANNOTATION_EXISTS`, `HASH_MISMATCH`, `LEGACY_UNVERIFIABLE`, and `OPERATION_NOT_FOUND`

The full schema is documented in [docs/PROTOCOL_JSON.md](docs/PROTOCOL_JSON.md).

## Safety Rules

SurePython currently enforces these principles:

- one operation changes at most one file
- one operation targets one symbol
- modification is refused when the Git worktree is not clean
- modification is refused outside the authorized project root
- existing docstrings are never replaced
- ambiguous targets are refused
- `Class.method` targets do not modify global functions with the same name
- `Class.method` targets do not modify methods in other classes
- `--dry-run` does not write the target file
- `--dry-run` does not run pytest
- `--test` runs after a real edit and returns an error when pytest fails
- `add-return-type` refuses existing return annotations
- `add-return-type` does not infer types
- `add-return-type` does not add imports
- `add-return-type` does not modify parameters or function bodies
- rollback requires `--db`
- rollback verifies `after_sha256` before reconstructing
- rollback verifies `before_sha256` before writing
- rollback writes bytes only after the restored bytes have already been validated

If SurePython hesitates, it refuses.

## SQLite Logging

The SQLite table is `surepython_operations`.

Current fields include:

- `created_at`
- `project_path`
- `file_path`
- `operation`
- `symbol`
- `before_sha256`
- `after_sha256`
- `git_diff`
- `pytest_command`
- `pytest_exit_code`
- `pytest_status`
- `status`
- `message`
- `source_operation_id`

Real operations with `--db` log automatically. Dry-runs and refusals do not create SQLite rows. `surepython log --db` remains a manual replay command for the last local operation state.

## Rollback Contract

Rollback supports this narrow case:

```text
latest compatible SQLite record
operation in add-docstring/add-return-type
status in applied/tested/failed
current file hash = logged after_sha256
restored bytes hash = logged before_sha256
```

Explicit rollback by operation id follows the same contract, but selects a single record with `--id <operation_id>` instead of the latest compatible record.

For current coherent records, rollback restores LF, CRLF, final newline, and UTF-8 BOM state byte for byte.

Historical records can be `legacy/unverifiable` when their `before_sha256` cannot be reconstructed from the logged operation. In that case, SurePython refuses without writing. It does not edit the historical hash and does not use Git as an unplanned substitute source of truth.

## Current Phase History

- Phase 1.0: minimal secure pipeline
- Phase 1.1: official dependencies and removal of behavioral shims
- Phase 1.2: explicit `Class.method` targeting
- Phase 1.3: structured scan formats
- Phase 1.4: dry-run previews
- Phase 1.5: pytest integration
- Phase 1.6: automatic SQLite logging for `add-docstring`
- Phase 1.7: explicit rollback for logged `add-docstring` operations
- Phase 1.8: product documentation and agent usage policy
- Phase 2.0: machine-readable capabilities and second proven operation, `add-return-type`
- Phase 2.1: agent-safe structured JSON protocol
- Phase 2.2: explicit rollback by operation id and self-hosting comparison

The public tag `v0.1.2-public-preview` remains an earlier frozen preview. Later commits document and extend the phase 1 line without moving that tag.

## Documentation

- [French tutorial](docs/TUTORIAL_FR.md)
- [Codex integration policy](docs/CODEX_INTEGRATION.md)
- [Reusable AGENTS template](docs/AGENTS_TEMPLATE.md)
- [Self-hosting policy](docs/SELF_HOSTING.md)
- [JSON protocol](docs/PROTOCOL_JSON.md)
- [Windows troubleshooting](docs/WINDOWS_TROUBLESHOOTING.md)

## Local Environment Notes

The project requires Python 3.12 or newer.

Dependencies are declared in `pyproject.toml`:

- `libcst`
- `pytest`

This repository may contain local bootstrap infrastructure such as `.vendor3` and `sitecustomize.py` to work around Windows workspace ACL issues. These are environment bootstraps, not behavioral shims for `libcst` or `pytest`.

See [Windows troubleshooting](docs/WINDOWS_TROUBLESHOOTING.md) before diagnosing rollback or pytest failures as SurePython defects.

## Roadmap Boundaries

SurePython does not yet provide:

- general Python rewriting
- arbitrary codemods
- multi-file edits
- automatic type inference
- import insertion for annotations
- interactive rollback selection
- rollback by date range
- Git-based restoration
- `scan --format xml`
- automatic pull request creation

The next public preview should be tagged only after documentation review, a clean Python 3.12 environment rebuild, full test validation, CRLF smoke validation, Markdown link checks, and a clean worktree.
