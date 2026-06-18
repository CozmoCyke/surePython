# SurePython

SurePython is a safety layer between AI-generated Python changes and real code.

Codex may propose, but SurePython verifies, limits, applies, shows the diff, runs tests, logs the operation, and can roll back the supported change when the log proves it is safe.

The name carries two meanings:

- safe Python
- Python you can be sure about

## What SurePython Is Today

SurePython is a local CLI for controlled Python micro-modifications.

It is not a general refactoring engine. It currently supports a deliberately small set of edits:

- add one skeleton docstring to one targeted Python function or method, only when the target has no existing docstring
- remove one exact docstring from one targeted Python module, class, function, or method after verifying the expected logical text
- add one explicit return annotation to one targeted Python function or method, only when the target has no existing return annotation
- remove one explicit return annotation from one targeted Python function or method after verifying the expected annotation
- add one explicit annotation to one targeted Python parameter, only when that parameter has no existing annotation
- remove one explicit annotation from one targeted Python parameter after verifying the expected annotation
- add one explicit top-level import statement with a single binding to one module file, only when that binding does not already exist
- remove one exact top-level import statement from one module file after verifying the expected statement
- add one explicit decorator expression to one targeted Python function, method, or class, only when the decorator is not already present and the target is unambiguous
- remove one explicit decorator expression from one targeted Python function, method, or class after verifying the expected expression and position
- preview, apply, rollback, or recover a transactional multi-operation plan that composes supported atomic edits

The working pipeline is:

```text
capabilities -> scan -> dry-run -> supported operation -> pytest -> SQLite log -> rollback
capabilities -> scan -> plan preview -> plan apply -> pytest -> SQLite log -> plan rollback / plan recover
```

This small scope is intentional. SurePython is designed to refuse when it cannot prove the operation.
The current supported edit set also includes safe explicit import removal by exact statement match and safe explicit docstring removal by expected text match.

## Trust Model

SurePython separates reasoning from execution:

- Codex can explore, explain, and propose broad changes.
- SurePython executes only the transformations it knows how to locate, verify, apply, test, log, and restore.
- Git shows the scar.
- Pytest checks the vital signs.
- SQLite and Datasette keep the medical record.

A refusal is not a failure of the tool. A refusal protects the project.

## Public Contract Freeze

Phase 3.2 freezes the public contract before the release candidate.

The canonical snapshots are:

- `contracts/public_contract_v1.json`
- `contracts/cli_contract_v1.json`
- `contracts/capabilities_v1.json`
- `contracts/error_registry_v1.json`
- `contracts/protocol_envelope_v1.json`
- `contracts/plan_schema_v1.json`
- `contracts/sqlite_schema_v1.json`
- `contracts/fixtures/preview_hash_vectors.json`

The validator is:

```powershell
python tools/check_contracts.py
```

It compares the current code against the frozen contract and validates the normative docs.

## Phase 3.1 Hardening

Phase 3.1 keeps the same public operation set, but hardens how transactional work happens:

- plan commands and mutating operations now take a project mutation lock so concurrent writers refuse with `PROJECT_MUTATION_LOCKED`
- transactional manifests are written atomically and carry a schema version plus a payload checksum
- recovery distinguishes invalid state, invalid manifest payloads, and conflicting incomplete manifests
- fault injection checkpoints exist only for tests and crash-recovery smokes

Recovery remains conservative: if SurePython cannot prove the state transition, it refuses instead of guessing.

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
python -m surepython remove-docstring tests\fixtures\sample_module.py --symbol SampleClass.sample_method --expect-docstring "Build a service." --dry-run
python -m surepython remove-docstring tests\fixtures\sample_module.py --symbol SampleClass.sample_method --expect-docstring "Build a service." --test --db .\surepython_lab.db
python -m surepython remove-docstring tests\fixtures\sample_module.py --symbol SampleClass.sample_method --expect-docstring "Build a service." --dry-run --format json
```

`remove-docstring` accepts:

- `--symbol NAME`
- `--expect-docstring "<exact docstring text>"`
- `--dry-run`
- `--test`
- `--test-command "<command>"`
- `--db <sqlite-path>`

`remove-docstring` removes exactly one docstring from one targeted module, class, function, or method after verifying the expected logical docstring text. It refuses when the docstring is missing, mismatched, unsupported, or represented in an inline suite.

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
python -m surepython remove-return-type src\service.py --function UserService.load_user --expect-annotation "User | None" --dry-run
python -m surepython remove-return-type src\service.py --function UserService.load_user --expect-annotation "User | None" --test --db .\surepython_lab.db
python -m surepython remove-return-type src\service.py --function UserService.load_user --expect-annotation "User | None" --dry-run --format json
```

`remove-return-type` accepts:

- `--function NAME`
- `--function Class.method`
- `--expect-annotation "<exact return annotation>"`
- `--dry-run`
- `--test`
- `--test-command "<command>"`
- `--db <sqlite-path>`

`remove-return-type` compares the expected annotation against the target's actual return annotation before removing it. It refuses when the annotation is absent or does not match.

```powershell
python -m surepython add-parameter-type src\service.py --function UserService.load_user --parameter source --annotation "str" --dry-run
python -m surepython add-parameter-type src\service.py --function UserService.load_user --parameter source --annotation "str" --test --db .\surepython_lab.db
python -m surepython add-parameter-type src\service.py --function UserService.load_user --parameter source --annotation "str" --dry-run --format json
```

`add-parameter-type` accepts:

- `--function NAME`
- `--function Class.method`
- `--parameter NAME`
- `--annotation "<type expression>"`
- `--dry-run`
- `--test`
- `--test-command "<command>"`
- `--db <sqlite-path>`

SurePython never infers a parameter annotation. Codex or a human proposes it; SurePython validates and inserts it exactly.

`add-parameter-type` supports positional-only, positional-or-keyword, and keyword-only parameters. It refuses variadic parameters (`*args` and `**kwargs`).

```powershell
python -m surepython remove-parameter-type src\service.py --function UserService.load_user --parameter source --expect-annotation "str" --dry-run
python -m surepython remove-parameter-type src\service.py --function UserService.load_user --parameter source --expect-annotation "str" --test --db .\surepython_lab.db
python -m surepython remove-parameter-type src\service.py --function UserService.load_user --parameter source --expect-annotation "str" --dry-run --format json
```

`remove-parameter-type` accepts:

- `--function NAME`
- `--function Class.method`
- `--parameter NAME`
- `--expect-annotation "<exact type expression>"`
- `--dry-run`
- `--test`
- `--test-command "<command>"`
- `--db <sqlite-path>`

`remove-parameter-type` compares the expected annotation against the exact current parameter annotation before removing it. It refuses when the annotation is absent, does not match, or the parameter is variadic.

```powershell
python -m surepython add-import parser.py --statement "import json" --dry-run
python -m surepython add-import parser.py --statement "from pathlib import Path" --test --db .\surepython_lab.db
python -m surepython add-import parser.py --statement "from pathlib import Path" --dry-run --format json
```

`add-import` accepts:

- `--statement "<exact import statement>"`
- `--dry-run`
- `--test`
- `--test-command "<command>"`
- `--db <sqlite-path>`

`add-import` supports exactly one top-level import statement with one binding. Supported forms include:

- `import json`
- `import numpy as np`
- `from pathlib import Path`
- `from typing import Any as TypingAny`

It refuses multi-binding imports, wildcard imports, relative imports, and binding conflicts. Codex or a human supplies the exact import statement; SurePython does not infer it.

```powershell
python -m surepython remove-import parser.py --expect-statement "import json" --dry-run
python -m surepython remove-import parser.py --expect-statement "from pathlib import Path" --test --db .\surepython_lab.db
python -m surepython remove-import parser.py --expect-statement "from pathlib import Path" --dry-run --format json
```

`remove-import` accepts:

- `--expect-statement "<exact import statement>"`
- `--dry-run`
- `--test`
- `--test-command "<command>"`
- `--db <sqlite-path>`

`remove-import` removes exactly one module-level import statement that matches the expected statement structurally and textually. It refuses nested-only matches, ambiguous matches, wildcard imports, relative imports, and multi-binding or syntax-invalid statements.

```powershell
python -m surepython add-decorator src\service.py --symbol UserService.load_user --decorator "staticmethod" --position outermost --dry-run
python -m surepython add-decorator src\service.py --symbol UserService.load_user --decorator "staticmethod" --position outermost --test --db .\surepython_lab.db
python -m surepython add-decorator src\service.py --symbol UserService.load_user --decorator "staticmethod" --position outermost --dry-run --format json
```

`add-decorator` accepts:

- `--symbol NAME`
- `--decorator "<exact decorator expression>"`
- `--position outermost|innermost`
- `--dry-run`
- `--test`
- `--test-command "<command>"`
- `--db <sqlite-path>`

`add-decorator` supports functions, async functions, methods, async methods, and classes. It refuses duplicate decorators, decorator conflicts such as incompatible binding helpers, ambiguous targets, and unsupported decorator expressions. The decorator expression is supplied explicitly; SurePython validates and inserts it exactly.

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

`rollback` is explicit, database-backed, and limited to compatible logged `add-docstring`, `remove-docstring`, `add-return-type`, `remove-return-type`, `add-parameter-type`, `remove-parameter-type`, `add-import`, `remove-import`, `add-decorator`, or `remove-decorator` operations. It supports either `--last` or `--id <operation_id>`, but never both.

```powershell
python -m surepython plan preview plan.json --format json
python -m surepython plan apply plan.json --expect-preview-hash sha256:... --test --db .\surepython_plans.db --format json
python -m surepython plan rollback --last --db .\surepython_plans.db --format json
python -m surepython plan rollback --id 42 --db .\surepython_plans.db --format json
python -m surepython plan recover --format json
```

`plan` is SurePython's transactional multi-operation layer. It previews a grouped JSON plan, applies the supported steps only when the preview hash matches, logs the plan as grouped SQLite records, and can roll back or recover an interrupted transaction. The plan file schema is documented in [docs/PLAN_SCHEMA_V1.md](docs/PLAN_SCHEMA_V1.md) and the workflow is documented in [docs/TRANSACTIONAL_PLANS.md](docs/TRANSACTIONAL_PLANS.md).

## Agent Protocol

SurePython phase 2.1 adds a stable JSON protocol for agents.

- request `--format json` explicitly
- parse `protocol_schema_version`
- use `capabilities --format json` before selecting an operation
- expect `operation_id` only for real SQLite writes
- expect dry-runs to return `operation_id: null`
- expect refusal codes such as `ANNOTATION_EXISTS`, `DECORATOR_ALREADY_EXISTS`, `HASH_MISMATCH`, `IMPORT_ALREADY_EXISTS`, `LEGACY_UNVERIFIABLE`, and `OPERATION_NOT_FOUND`

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
- `remove-return-type` refuses absent return annotations
- `remove-return-type` refuses mismatched expected annotations
- `remove-return-type` does not infer types
- `remove-return-type` does not add imports
- `remove-return-type` does not modify parameters or function bodies
- `add-parameter-type` refuses existing parameter annotations
- `add-parameter-type` does not infer parameter types
- `add-parameter-type` refuses variadic parameters
- `add-parameter-type` does not add imports
- `add-parameter-type` does not modify function bodies
- `remove-parameter-type` refuses absent parameter annotations
- `remove-parameter-type` refuses mismatched expected annotations
- `remove-parameter-type` refuses variadic parameters
- `remove-parameter-type` does not infer parameter types
- `remove-parameter-type` does not add imports
- `remove-parameter-type` does not modify function bodies
- `add-import` refuses multiple bindings
- `add-import` refuses wildcard imports
- `add-import` refuses relative imports
- `add-import` refuses binding conflicts
- `add-import` does not infer imports
- `add-import` does not rewrite or sort existing imports
- `add-decorator` refuses duplicate decorators
- `add-decorator` refuses incompatible decorator conflicts
- `add-decorator` does not infer decorators
- `add-decorator` does not modify the body beyond the decorator list
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
- `import_statement`
- `import_binding`
- `decorator_expression`
- `decorator_position`
- `decorator_target_kind`
- `parameter`
- `target_kind`
- `parameter_kind`
- `expected_parameter_annotation`
- `parameter_annotation`
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
latest compatible SQLite record or selected operation id
operation in add-docstring/remove-docstring/add-return-type/remove-return-type/add-parameter-type/remove-parameter-type/add-import/remove-import/add-decorator/remove-decorator
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
- Phase 2.3: safe parameter annotation edits
- Phase 2.4: safe explicit import insertion and expanded self-hosting
- Phase 2.5: safe explicit decorator insertion
- Phase 2.6: safe return annotation removal by explicit comparison
- Phase 2.7: safe parameter annotation removal by explicit comparison
- Phase 2.8: safe explicit decorator removal
- Phase 2.9: safe explicit import removal
- Phase 2.10: safe explicit docstring removal
- Phase 3.0: transactional multi-operation plans and recovery

The public tag `v0.1.2-public-preview` remains an earlier frozen preview. Later commits document and extend the phase 1 line without moving that tag.

## Documentation

- [French tutorial](docs/TUTORIAL_FR.md)
- [Codex integration policy](docs/CODEX_INTEGRATION.md)
- [Reusable AGENTS template](docs/AGENTS_TEMPLATE.md)
- [Self-hosting policy](docs/SELF_HOSTING.md)
- [Transactional plans](docs/TRANSACTIONAL_PLANS.md)
- [Plan schema v1](docs/PLAN_SCHEMA_V1.md)
- [JSON protocol](docs/PROTOCOL_JSON.md)
- [Windows troubleshooting](docs/WINDOWS_TROUBLESHOOTING.md)

## Local Environment Notes

The project requires Python 3.12 or newer.

Dependencies are declared in `pyproject.toml`:

- `libcst`
- `pytest`

This repository may contain local bootstrap infrastructure such as `.vendor3` and `sitecustomize.py` to work around Windows workspace ACL issues. These are environment bootstraps, not behavioral shims for `libcst` or `pytest`.

See [Windows troubleshooting](docs/WINDOWS_TROUBLESHOOTING.md) before diagnosing rollback or pytest failures as SurePython defects.

## Packaging And Distribution

Phase 3.3 prepares SurePython for clean distribution on Windows, Linux, and macOS.

The packaging contract now includes:

- wheel and sdist builds from a clean tree
- clean installs into fresh virtual environments
- uninstall verification
- embedded package resources for the frozen contracts
- a release validator script at `tools/check_release.py`
- packaging metadata validation in `tests/test_packaging_metadata.py`

The release process is documented in:

- `docs/INSTALLATION.md`
- `docs/BUILDING.md`
- `docs/SUPPORTED_PLATFORMS.md`
- `docs/RELEASE_PROCESS.md`
- `docs/DISTRIBUTION_SECURITY.md`

SurePython remains a narrow safety layer. Packaging does not expand the supported edit set; it only proves that the tool can be built, installed, validated, and removed cleanly.

## Roadmap Boundaries

SurePython does not yet provide:

- general Python rewriting
- arbitrary codemods
- multi-file edits
- automatic type inference
- import insertion for annotations
- automatic import inference or rewriting
- automatic import insertion without an explicit statement
- interactive rollback selection
- rollback by date range
- Git-based restoration
- `scan --format xml`
- automatic pull request creation

The next public preview should be tagged only after documentation review, a clean Python 3.12 environment rebuild, full test validation, CRLF smoke validation, Markdown link checks, and a clean worktree.
