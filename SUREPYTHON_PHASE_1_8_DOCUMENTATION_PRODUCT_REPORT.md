# SurePython Phase 1.8 Documentation Product Report

## Objective

Phase 1.8 turns the accumulated technical reports into product-facing documentation and an agent usage policy.

This phase is documentation-only.

## Files Added Or Rewritten

- `README.md`
- `docs/TUTORIAL_FR.md`
- `docs/CODEX_INTEGRATION.md`
- `docs/AGENTS_TEMPLATE.md`
- `docs/WINDOWS_TROUBLESHOOTING.md`
- `SUREPYTHON_PHASE_1_8_DOCUMENTATION_AUDIT.md`
- `SUREPYTHON_PHASE_1_8_DOCUMENTATION_PRODUCT_REPORT.md`

## Product Message

SurePython is a safety layer between AI-generated Python changes and real code.

Codex may propose broadly. SurePython executes only the transformations it can prove.

Current proven pipeline:

```text
scan -> dry-run -> add-docstring -> pytest -> SQLite log -> rollback
```

## Documentation Layers

### README

The README is now the product entry point. It explains:

- what SurePython is
- what it does today
- the trust model
- supported commands
- safety rules
- SQLite logging
- rollback contract
- phase history
- current roadmap boundaries

### Tutorial FR

`docs/TUTORIAL_FR.md` provides a French, reproducible path through:

- environment preparation
- scan
- dry-run
- real operation
- pytest
- SQLite logging
- rollback dry-run
- real rollback
- validation checklist

### Codex Integration

`docs/CODEX_INTEGRATION.md` defines:

- what Codex may do
- what SurePython may do
- how Codex should use SurePython commands
- how refusals must be handled
- what Codex must not infer

### AGENTS Template

`docs/AGENTS_TEMPLATE.md` provides a reusable project policy for agentic workflows that use SurePython.

### Windows Troubleshooting

`docs/WINDOWS_TROUBLESHOOTING.md` separates:

- environment issues such as `.venv`, Hermes-style launcher confusion, and ACLs
- file preservation issues such as LF, CRLF, BOM, and final newline
- historical proof issues such as `legacy/unverifiable`

## Guarantees Preserved

This phase does not:

- modify `surepython/*.py`
- modify behavioral tests
- modify `pyproject.toml`
- add commands
- add codemods
- change SQLite schema
- move or create tags
- push to GitHub

## Validation Plan

Required checks:

```powershell
git diff --check
git diff --name-only
git status --short
python -m surepython --help
python -m surepython scan --help
python -m surepython add-docstring --help
python -m surepython rollback --help
python -m surepython scan tests\fixtures --format json
python -m surepython add-docstring tests\fixtures\sample_module.py --function SampleClass.sample_method --dry-run
python -m surepython diff
```

Markdown local links should also be checked before review.

## Before The Next Public Preview

Do not create a new tag until:

- documentation has been reviewed
- the French tutorial has been executed by a person end to end
- a clean Python 3.12 `.venv` has been recreated
- the full test suite passes in that `.venv`
- the CRLF rollback smoke path is confirmed
- Markdown links are checked
- worktree is clean
- `main` and `origin/main` are aligned

The existing public tag `v0.1.2-public-preview` must remain unchanged.
