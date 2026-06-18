# Transactional Plans

SurePython phase 3.0 adds a grouped `plan` command for multi-step changes that must be previewed, applied, logged, rolled back, and recovered together.

The frozen plan contract is captured in `contracts/plan_schema_v1.json` and validated together with the protocol and capability snapshots under `contracts/`.

## Supported Commands

```powershell
python -m surepython plan preview plan.json --format json
python -m surepython plan apply plan.json --expect-preview-hash sha256:... --test --db .\surepython_plans.db --format json
python -m surepython plan rollback --last --db .\surepython_plans.db --format json
python -m surepython plan rollback --id 42 --db .\surepython_plans.db --format json
python -m surepython plan recover --format json
```

## Plan File Contract

A transactional plan is a JSON object with:

- `plan_schema_version`
- optional `name`
- optional `description`
- optional `client_plan_id`
- optional `metadata`
- `steps`

Each step must contain:

- `id`
- `operation`
- `file`
- `arguments`

The supported step operations are the same atomic SurePython edits already published through `capabilities`.

## Preview Hash

`plan preview` returns a deterministic `preview_hash` with the prefix `sha256:`.

`plan apply` refuses unless the caller supplies the exact preview hash that matches the current project state.

## Logging

Transactional plans are logged to SQLite as a grouped plan record plus step and file records. The log stores:

- the plan identity
- the ordered steps
- the touched files
- before/after SHA-256 values
- the preview hash
- the test result if `--test` was requested

## Rollback

`plan rollback` rolls back a previously logged plan, not an individual atomic codemod.

It supports:

- `--last`
- `--id <plan_operation_id>`

Rollback refuses if:

- the plan already has a rollback record
- the selected plan belongs to another project
- the current file hashes do not match the recorded plan state
- the plan manifest requires recovery

## Recovery

If an apply or rollback is interrupted, SurePython writes a manifest and preimages into a transaction workspace outside the Git tree.

`plan recover` restores interrupted files from those preimages without changing the Git worktree itself.

The transaction workspace lives outside the repository tree so that interrupted plan bookkeeping does not dirty the worktree or require repository-local ignore rules.
