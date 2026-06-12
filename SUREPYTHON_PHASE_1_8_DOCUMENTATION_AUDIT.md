# SurePython Phase 1.8 Documentation Audit

## Purpose

This audit was performed before writing Phase 1.8 documentation.

Phase 1.8 is documentation-only. It does not change the SurePython engine, tests, SQLite schema, commands, tags, or GitHub publication state.

## Repository State At Audit Start

- Branch requested: `docs/phase-1.8`
- Baseline commit: `772df2cc86ae5f6ea9920f3bf67aa9d145792c00`
- `main` and `origin/main` were aligned before branching
- Public tag `v0.1.2-public-preview` remains fixed on `5e3a0591581fcc735b828688793b91eb008d5ef2`
- Worktree was clean before documentation edits

## CLI Confirmed

Read-only CLI help confirmed these commands:

- `scan`
- `add-docstring`
- `diff`
- `log`
- `rollback`

Confirmed options:

- `scan PATH --format {text,json,csv}`
- `add-docstring FILE --function SYMBOL [--test] [--test-command CMD] [--dry-run] [--db PATH]`
- `diff`
- `log --db PATH`
- `rollback --last --db PATH [--dry-run]`

## Code Contracts Confirmed

From `surepython/cli.py`, `surepython/codemods.py`, `surepython/datasette_log.py`, and `surepython/rollback.py`:

- `scan` serializes text, JSON, and CSV with the expected fields.
- `add-docstring` targets one function or method.
- `Class.method` is treated as an explicit class-scoped target.
- `--dry-run` computes a preview diff without writing the target file.
- `--dry-run` does not launch pytest.
- `--test` runs after a real edit.
- `run_pytest()` uses the current Python executable with `-m pytest` unless a test command is provided.
- `--db` on `add-docstring` writes an automatic SQLite operation record.
- `surepython log --db` remains a manual replay path for the last local operation state.
- `rollback --last --db` reads the latest compatible `add-docstring` record.
- rollback refuses when required hashes or fields are missing or incompatible.
- rollback writes restored bytes only after matching `before_sha256`.

## SQLite Fields Confirmed

The `surepython_operations` table currently stores:

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

## Test Coverage Confirmed

The test suite covers:

- scan text output
- scan JSON output
- scan CSV output
- unknown scan format refusal
- global function docstring insertion
- explicit `Class.method` targeting
- same method name in another class not being modified
- same name global function not being modified
- existing docstring refusal
- dry-run without file write
- dry-run with SQLite `planned` log
- pytest runner isolation
- pytest success and failure reporting
- automatic SQLite logging
- rollback dry-run
- real rollback
- LF byte-exact rollback
- CRLF byte-exact rollback
- final newline preservation
- rollback refusal when Git is dirty
- rollback refusal on hash mismatch
- Windows-style add-docstring, commit, rollback smoke coverage

## Documentation Risks Identified

The documentation must avoid implying that SurePython is:

- a general Python development engine
- a general codemod runner
- a multi-file refactoring tool
- a Git-based restoration system
- an automatic rollback system
- able to repair historical SQLite records

The documentation must clearly distinguish:

- what SurePython does today
- what SurePython verifies
- what remains future roadmap

## Windows Notes Confirmed

Prior project history includes local environment issues:

- broken `.venv` launchers can point to removed Python installations
- Python launcher or managed runtime confusion can occur
- pytest temporary directory ACL issues can prevent test startup
- `.vendor3` and `sitecustomize.py` are environment bootstrap infrastructure, not behavioral shims
- rollback must preserve LF, CRLF, final newline, and UTF-8 BOM state
- `legacy/unverifiable` records must be refused without writing

## Phase 1.8 Documentation Plan

Documents to create or update:

- `README.md`
- `docs/TUTORIAL_FR.md`
- `docs/CODEX_INTEGRATION.md`
- `docs/AGENTS_TEMPLATE.md`
- `docs/WINDOWS_TROUBLESHOOTING.md`
- `SUREPYTHON_PHASE_1_8_DOCUMENTATION_PRODUCT_REPORT.md`

No core code or behavioral tests should be modified.
