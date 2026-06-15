# SurePython Phase 2.7 Pre-Merge Review

## Verdict

Ready for transfer after one correction.

## Review Scope

Phase 2.7 adds `remove-parameter-type`, a compare-and-remove codemod that removes exactly one explicit parameter annotation after verifying the expected annotation.

## Delta Inspected

Reviewed changes in:

- `surepython/codemods.py`
- `surepython/rollback.py`
- `surepython/cli.py`
- `surepython/datasette_log.py`
- `surepython/protocol.py`
- `surepython/capabilities.py`
- `tests/test_remove_parameter_type.py`
- `tests/test_capabilities.py`
- `README.md`
- `AGENTS.md`
- `docs/CODEX_INTEGRATION.md`
- `docs/AGENTS_TEMPLATE.md`
- `docs/PROTOCOL_JSON.md`
- `docs/SELF_HOSTING.md`
- `docs/TUTORIAL_FR.md`
- `docs/WINDOWS_TROUBLESHOOTING.md`
- the phase 2.7 reports

## Findings

One contract issue was found and corrected during review:

- `PARAMETER_AMBIGUOUS` was advertised in protocol/capabilities even though Python signatures do not have a valid, separately handled ambiguity state for parameter names.
- The code path did not produce that error code.
- The code, capabilities, protocol documentation, and capability tests were updated to remove it.

No other blocking defects were found.

## Supported Behavior Confirmed

`remove-parameter-type` now:

- targets an exact function or method
- targets an exact parameter
- requires an exact expected annotation
- compares the current annotation before removal
- removes only the requested parameter annotation
- preserves default values
- preserves neighboring parameters
- preserves `/`, `*`, return annotations, decorators, and the body
- refuses `*args` and `**kwargs`
- logs automatically when `--db` is provided
- supports rollback by `--last` and `--id`

## Contract Checks

Confirmed in the implementation and tests:

- `PARAMETER_REQUIRED`
- `PARAMETER_NOT_FOUND`
- `PARAMETER_KIND_UNSUPPORTED`
- `PARAMETER_ANNOTATION_REQUIRED`
- `PARAMETER_ANNOTATION_INVALID`
- `PARAMETER_ANNOTATION_NOT_FOUND`
- `PARAMETER_ANNOTATION_MISMATCH`
- `TARGET_NOT_FOUND`
- `TARGET_AMBIGUOUS`
- `TARGET_UNSUPPORTED`
- `FILE_NOT_FOUND`
- `FILE_OUTSIDE_PROJECT`
- `PARSE_ERROR`
- `GIT_DIRTY`
- `TESTS_FAILED`
- `DATABASE_ERROR`
- `INTERNAL_ERROR`

## Comparisons And Preservation

Confirmed coverage includes:

- positional-only parameters
- positional-or-keyword parameters
- keyword-only parameters
- `self`
- `cls`
- default values
- multiline signatures
- return annotations
- decorators
- byte-exact rollback
- LF / CRLF / BOM preservation

## JSON And Capabilities

Confirmed:

- `protocol_schema_version = "1.0"`
- `capabilities_schema_version = "1.0"`
- `remove-parameter-type` is declared in the capabilities registry
- JSON output remains deterministic and structured
- rollback remains a separate command capability

## SQLite

Confirmed additive logging support for:

- `target_kind`
- `parameter_kind`
- `expected_parameter_annotation`
- `parameter_annotation`

The migration is nullable and additive, and the historical tables remain readable.

## Rollback

Confirmed rollback support for:

- `rollback --last`
- `rollback --id <operation_id>`

Confirmed protections:

- double rollback is refused
- project mismatch is refused
- hash mismatch is refused
- legacy / unverifiable records are refused
- rollback remains byte-exact for supported records

## Validation

Executed:

- `python -m pytest`
- `python -m surepython capabilities --format json`
- `python -m surepython scan surepython --format json`
- `python -m surepython diff`
- `git diff --check`

Final test result:

- `194 passed`

## Recommendation

Proceed to transfer Phase 2.7 after this review commit.

The implementation is sound for the supported contract, and the only contract mismatch has already been corrected.
