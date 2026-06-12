# SurePython

SurePython is a safety layer between AI-generated Python changes and real code.
Codex may propose, but SurePython verifies, limits, applies, shows the diff, runs tests, and logs the operation.

It also carries a second meaning in French: Python safe, or Python we can be sure about.

## Mission

SurePython is a local trust boundary for controlled Python micro-changes.

Pipeline:

1. Codex proposes.
2. SurePython verifies and limits.
3. SurePython applies a single, targeted change.
4. Git diff confirms the result.
5. Pytest validates the change.
6. SQLite and Datasette keep the audit trail.

## Available Commands

- `scan`
- `add-docstring`
- `diff`
- `log`

## Safety Rules

- One file per operation.
- One symbol per operation.
- Refuse if git is not clean.
- Refuse outside the authorized project root.
- Refuse if a docstring already exists.
- Refuse ambiguous targets.
- Refuse silent edits.
- Never do a global rewrite.

## Current State

- Phase 1.0: minimal secure pipeline
- Phase 1.1: official dependencies, behavioral shims removed
- Phase 1.2: explicit `Class.method` targeting

## Examples

```powershell
python -m surepython scan .
python -m surepython add-docstring tests\fixtures\sample_module.py --function sample_function --test
python -m surepython add-docstring tests\fixtures\sample_module.py --function SampleClass.sample_method
python -m surepython diff
python -m surepython log --db .\didier_lab.db
```

## Local Environment Note

The local `.vendor3` tree and `sitecustomize.py` bootstrap remain in place as an environment fix for ACL issues in this workspace.
They are documented as bootstrap infrastructure, not behavioral shims.
