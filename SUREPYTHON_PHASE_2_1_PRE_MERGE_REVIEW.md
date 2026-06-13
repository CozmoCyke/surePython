# SurePython Phase 2.1 Pre-Merge Review

Repository: `C:\dev\datasette-lab\surePython`

Branch: `feature/phase-2.1-agent-protocol`

HEAD: `347806c9fa518b17bb45f8948d6df5f8ced2f96b`

Base branch: `origin/main` at `4f13f44158cc6e156c35084f439238552d86ab3d`

Public tag: `v0.3.0-public-preview` at `4f13f44158cc6e156c35084f439238552d86ab3d`

## Summary

Phase 2.1 adds a structured protocol layer for SurePython without changing the core micro-modification semantics. The branch is clean, the protocol JSON is deterministic, and the structured commands keep stdout parseable. The implementation now exposes a stable agent-facing contract while preserving the legacy human text behavior.

## Delta Inspected

The branch delta against `origin/main` is limited to:

- `surepython/protocol.py`
- `surepython/capabilities.py`
- `surepython/cli.py`
- `surepython/codemods.py`
- `surepython/datasette_log.py`
- `surepython/git_tools.py`
- `surepython/rollback.py`
- `tests/test_protocol_json.py`
- updates to existing add-docstring, add-return-type, capabilities, and rollback tests
- documentation updates in `README.md`, `docs/PROTOCOL_JSON.md`, `docs/TUTORIAL_FR.md`, `docs/CODEX_INTEGRATION.md`, `docs/AGENTS_TEMPLATE.md`
- implementation and architecture reports for Phase 2.1

No third codemod was added. No API server, MCP layer, or HTTP surface was introduced.

## Public Protocol Contract

Observed protocol schema:

- `protocol_schema_version`: `1.0`
- `capabilities_schema_version`: `1.0`
- supported operations: `add-docstring`, `add-return-type`

The structured payloads are deterministic and contain the expected top-level fields:

- `command`
- `ok`
- `status`
- `error`
- `result`
- `meta`

Structured JSON commands remain parseable on stdout with no human preamble.

## Stdout Purity

Verified commands:

- `surepython capabilities --format json`
- `surepython add-docstring ... --dry-run --format json`
- `surepython add-return-type ... --dry-run --format json`

Each produced valid JSON only on stdout, with empty stderr in the successful cases. The JSON was parseable with `json.loads` and repeated runs were deterministic.

## Error Codes and Exit Codes

The protocol centralizes error codes and exit mapping in `surepython/protocol.py`.

Notable codes present:

- `GIT_NOT_REPOSITORY`
- `GIT_DIRTY`
- `FILE_OUTSIDE_PROJECT`
- `FILE_NOT_FOUND`
- `PARSE_ERROR`
- `TARGET_NOT_FOUND`
- `TARGET_AMBIGUOUS`
- `TARGET_UNSUPPORTED`
- `DOCSTRING_EXISTS`
- `ANNOTATION_REQUIRED`
- `ANNOTATION_INVALID`
- `ANNOTATION_EXISTS`
- `UNSUPPORTED_OPERATION`
- `UNKNOWN_SQLITE_OPERATION`
- `HASH_MISMATCH`
- `LEGACY_UNVERIFIABLE`
- `TESTS_FAILED`
- `DATABASE_ERROR`
- `ROLLBACK_NOT_AVAILABLE`
- `INTERNAL_ERROR`

The exit mapping remains consistent:

- refused operations use the refusal exit path
- hash and legacy verification failures use the security exit path
- test failures use the tests-failed exit path
- internal/database failures use the internal exit path

## SQLite Operation IDs

The protocol distinguishes logged and unlogged operations correctly:

- dry-run preview: `operation_id = null`, `logged = false`, `rollback_available = false`
- real write without `--db`: `operation_id = null`, `logged = false`, `rollback_available = false`
- real write with `--db`: `operation_id` is non-null, `logged = true`, `rollback_available = true`

Rollback responses include a distinct rollback operation id and the source operation id.

## Rollback Structured Behavior

Rollback JSON remains structured and byte-exact for supported histories.

Verified behavior:

- rollback preview is JSON parseable
- rollback real uses the logged operation metadata
- `source_operation_id` is preserved
- the rollback log entry is distinct from the source entry
- `HASH_MISMATCH` and `LEGACY_UNVERIFIABLE` remain hard refusals
- unknown SQLite operations are rejected rather than interpreted creatively

## Text Compatibility

Default CLI text behavior remains available for historical workflows:

- `surepython capabilities`
- `surepython scan tests\\fixtures`
- `surepython add-docstring ... --dry-run`
- `surepython add-return-type ... --dry-run`
- `surepython diff`

The human-readable output still exists by default and keeps the original guardrails intact.

## Agent End-to-End Check

The structured contract supports the expected agent workflow:

1. read `capabilities --format json`
2. choose a supported operation
3. run a dry-run JSON preview
4. apply with `--test` and optionally `--db`
5. read the operation id
6. commit the result in Git if desired
7. roll back using the logged source operation

The branch currently satisfies the JSON parseability and rollback metadata requirements for that flow.

## Pytest Failure Path

The Phase 2.1 protocol distinguishes test failures from successful writes. `TESTS_FAILED` is surfaced as a structured error, and the JSON response remains parseable when tests fail.

## Documentation Review

Reviewed:

- `README.md`
- `docs/PROTOCOL_JSON.md`
- `docs/TUTORIAL_FR.md`
- `docs/CODEX_INTEGRATION.md`
- `docs/AGENTS_TEMPLATE.md`
- Phase 2.1 audit and implementation reports

The documentation now matches the structured protocol and the actual runtime behavior. One important clarification is documented: dry-runs and refusals do not create SQLite rows, while real logged operations do.

## Validation

Final validation run:

- `python -m pytest --basetemp .\\.tmp\\pytest_phase_2_1_pre_merge`
- `surepython capabilities --format json`
- `surepython scan tests\\fixtures --format json`
- `surepython add-docstring tests\\fixtures\\sample_module.py --function SampleClass.sample_method --dry-run --format json`
- `surepython add-return-type tests\\fixtures\\sample_module.py --function SampleClass.sample_method --annotation "str" --dry-run --format json`
- `surepython diff`
- `git diff --check`
- `git status --short`

Result:

- 68 tests passed
- JSON outputs were valid and deterministic
- stdout stayed clean for the structured commands
- diff remained empty
- worktree remained clean

## Findings

No blocking findings were identified in the Phase 2.1 pre-merge review.

Residual risk:

- the structured protocol is intentionally narrow; future protocol expansion should keep the schema versioned and backwards compatible

## Recommendation

Ready for transfer to `main`.

