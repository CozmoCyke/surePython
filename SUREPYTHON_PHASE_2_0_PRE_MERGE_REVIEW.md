# SurePython Phase 2.0 Pre-Merge Review

## Scope

This review inspected the Phase 2.0 feature branch before transfer to `main`.

Branch:

- `feature/phase-2.0-capabilities-return-type`

Head reviewed:

- `72e9b80ae9700becafd7b02bcd73807e22dd83f7`

Base branch:

- `origin/main` at `ddc75122af995826672e5ec92537e4d1a848480e`

## Files Inspected

- `surepython/capabilities.py`
- `surepython/cli.py`
- `surepython/codemods.py`
- `surepython/datasette_log.py`
- `surepython/rollback.py`
- `surepython/scanner.py`
- `surepython/__main__.py`
- `tests/test_add_docstring.py`
- `tests/test_add_return_type.py`
- `tests/test_capabilities.py`
- `tests/test_rollback.py`
- `tests/test_scan.py`
- `README.md`
- `docs/TUTORIAL_FR.md`
- `docs/CODEX_INTEGRATION.md`
- `docs/AGENTS_TEMPLATE.md`
- `docs/WINDOWS_TROUBLESHOOTING.md`
- `SUREPYTHON_PHASE_2_0_ARCHITECTURE_AUDIT.md`
- `SUREPYTHON_PHASE_2_0_IMPLEMENTATION_REPORT.md`

## Git Delta

The Phase 2.0 delta is centered on:

- a machine-readable capabilities registry
- the `capabilities` CLI command
- the `add-return-type` codemod
- rollback dispatch by operation type
- SQLite compatibility helpers
- tests
- documentation updates

No unrelated files were introduced.

## Capabilities Contract

`surepython capabilities --format json` returns a stable, deterministic JSON object with an `operations` list.

Validated fields per operation:

- `name`
- `description`
- `targets`
- `required_arguments`
- `supports_dry_run`
- `supports_tests`
- `supports_logging`
- `supports_rollback`
- `status`

The JSON contract currently exposes exactly:

- `add-docstring`
- `add-return-type`

The output is machine-readable and independent of the current workspace state.

## Backward Compatibility

Phase 1.x behavior remained intact during validation:

- `scan` still supports text, JSON, and CSV.
- `add-docstring --dry-run` still previews without writing.
- `diff` still shows the Git diff only.
- `log` still replays the last local operation state into SQLite.
- `rollback` still validates hashes before writing.

The `python -m surepython` launcher was hardened so CLI exit codes propagate correctly through `surepython/__main__.py`.

## Add-Docstring Results

Validation confirmed:

- global function targeting still works
- `Class.method` targeting still works
- dry-run still leaves the file unchanged
- Git cleanliness checks remain enforced
- rollback for existing `add-docstring` records still works
- LF, CRLF, and BOM preservation remain intact

## Add-Return-Type Results

Validation confirmed:

- simple function targets work
- qualified method targets work
- async function targets work
- `str`, `list[str]`, and `User | None` annotations are accepted syntactically
- existing return annotations are refused
- invalid annotations are refused
- missing targets are refused
- ambiguous unqualified names are refused
- dry-run does not write the file
- `--test` runs pytest after a real edit
- SQLite logging records the operation type and status
- rollback restores the original bytes byte for byte

Important nuance:

- `add-return-type` validates annotation syntax.
- it does not guarantee that every referenced name is runtime-resolvable in the target project.
- `--test` is the mechanism that reveals such failures.

## Rollback Review

Rollback now dispatches by operation type and recognizes:

- `add-docstring`
- `add-return-type`

Rollback continues to refuse:

- hash mismatches
- dirty Git state
- unsupported operation types
- historical `legacy/unverifiable` records

During review, one important correctness issue was hardened:

- rollback must refuse an unknown operation type instead of skipping past it and rolling back an older record.

That behavior is now covered by a dedicated regression test.

## SQLite Compatibility

No destructive schema migration was introduced.

The existing SQLite schema remains compatible with older `add-docstring` records.

Compatibility checks confirmed:

- old `add-docstring` records remain readable
- new `add-return-type` records are distinguished by `operation`
- unknown operation types are refused
- `legacy/unverifiable` records remain refusals without write-back

## Smoke Result

A real CRLF temporary-repository smoke test validated:

```text
CRLF file
-> add-return-type --test --db
-> commit
-> rollback --dry-run
-> rollback
-> byte-identical restoration
-> SQLite rollback / rolled_back
```

Bytes and hashes matched:

- `before_sha256 == restored_sha256`
- `bytes_equal == True`

## Documentation Review

The product docs were updated to describe:

- `capabilities`
- `capabilities --format json`
- `add-return-type`
- the explicit annotation contract
- the syntax-vs-runtime nuance for annotations
- the extended rollback and capability model

Reviewed docs remain aligned with the CLI surface.

## Corrections Made During Review

Corrections were limited to:

- refining rollback selection so unknown operations are refused explicitly
- adding a regression test for unknown SQLite operation types

No new codemods were added beyond `add-return-type`.

## Test Result

Final validation count:

```text
61 passed
```

## Residual Risks

- `add-return-type` accepts syntactically valid annotations that may still fail at runtime if the project cannot resolve the referenced names.
- Phase 2.0 still supports only two operations.
- No rollback-by-range, multi-rollback, or generic codemod framework exists yet.

## Recommendation

Phase 2.0 is ready for transfer to `main`.
