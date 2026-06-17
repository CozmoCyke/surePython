# SurePython JSON Protocol

This document defines the machine-readable contract used by SurePython phase 2.8.

## Versioning

- `protocol_schema_version`: `"1.0"`
- `capabilities_schema_version`: `"1.0"` for `surepython capabilities --format json`

The JSON protocol is stable for the commands supported in this phase:

- `capabilities`
- `add-docstring`
- `remove-docstring`
- `add-return-type`
- `remove-return-type`
- `add-parameter-type`
- `remove-parameter-type`
- `add-import`
- `remove-import`
- `add-decorator`
- `remove-decorator`
- `rollback`
- `plan`

## General Response Shape

Operational commands return an envelope with deterministic keys:

```json
{
  "protocol_schema_version": "1.0",
  "command": "add-return-type",
  "ok": true,
  "status": "preview",
  "error": null,
  "result": {},
  "meta": {}
}
```

Field meanings:

- `command`: the CLI command that ran
- `ok`: `true` only when the command completed successfully
- `status`: one of `preview`, `applied`, `tested`, `failed`, `rolled_back`, `recovered`, `noop`, or `refused`
- `error`: structured error object when `ok` is `false`
- `result`: command-specific payload, or `null` on refusal
- `meta`: request metadata such as `dry_run`

## Error Object

```json
{
  "code": "ANNOTATION_EXISTS",
  "message": "The target already has a return annotation.",
  "details": {
    "symbol": "AuditRunner.run"
  }
}
```

Error codes are stable and do not depend on the human wording of the message.

Common codes include:

- `GIT_NOT_REPOSITORY`
- `GIT_DIRTY`
- `FILE_NOT_FOUND`
- `FILE_OUTSIDE_PROJECT`
- `TARGET_NOT_FOUND`
- `TARGET_AMBIGUOUS`
- `TARGET_UNSUPPORTED`
- `DOCSTRING_EXISTS`
- `DOCSTRING_REQUIRED`
- `DOCSTRING_NOT_FOUND`
- `DOCSTRING_MISMATCH`
- `DOCSTRING_TARGET_UNSUPPORTED`
- `DOCSTRING_INLINE_SUITE_UNSUPPORTED`
- `ANNOTATION_REQUIRED`
- `ANNOTATION_INVALID`
- `ANNOTATION_EXISTS`
- `RETURN_ANNOTATION_REQUIRED`
- `RETURN_ANNOTATION_INVALID`
- `RETURN_ANNOTATION_NOT_FOUND`
- `RETURN_ANNOTATION_MISMATCH`
- `PARAMETER_REQUIRED`
- `PARAMETER_NOT_FOUND`
- `PARAMETER_ANNOTATION_EXISTS`
- `PARAMETER_KIND_UNSUPPORTED`
- `PARAMETER_ANNOTATION_REQUIRED`
- `PARAMETER_ANNOTATION_INVALID`
- `PARAMETER_ANNOTATION_NOT_FOUND`
- `PARAMETER_ANNOTATION_MISMATCH`
- `DECORATOR_REQUIRED`
- `DECORATOR_INVALID`
- `DECORATOR_POSITION_REQUIRED`
- `DECORATOR_POSITION_INVALID`
- `DECORATOR_NOT_FOUND`
- `DECORATOR_POSITION_MISMATCH`
- `DECORATOR_TARGET_UNSUPPORTED`
- `DECORATOR_ALREADY_EXISTS`
- `DECORATOR_CONFLICT`
- `IMPORT_STATEMENT_REQUIRED`
- `IMPORT_STATEMENT_INVALID`
- `IMPORT_MULTIPLE_BINDINGS_UNSUPPORTED`
- `IMPORT_WILDCARD_UNSUPPORTED`
- `IMPORT_RELATIVE_UNSUPPORTED`
- `IMPORT_ALREADY_EXISTS`
- `IMPORT_BINDING_CONFLICT`
- `IMPORT_PLACEMENT_UNSUPPORTED`
- `IMPORT_NOT_FOUND`
- `IMPORT_AMBIGUOUS`
- `IMPORT_SCOPE_UNSUPPORTED`
- `UNSUPPORTED_OPERATION`
- `UNKNOWN_SQLITE_OPERATION`
- `HASH_MISMATCH`
- `LEGACY_UNVERIFIABLE`
- `PROJECT_MUTATION_LOCKED`
- `TESTS_FAILED`
- `DATABASE_ERROR`
- `ROLLBACK_NOT_AVAILABLE`
- `OPERATION_ID_REQUIRED`
- `OPERATION_ID_INVALID`
- `OPERATION_NOT_FOUND`
- `ROLLBACK_SELECTOR_CONFLICT`
- `ROLLBACK_ALREADY_APPLIED`
- `ROLLBACK_RECORD_NOT_ALLOWED`
- `PROJECT_MISMATCH`
- `PLAN_INVALID_JSON`
- `PLAN_SCHEMA_UNSUPPORTED`
- `PLAN_INVALID`
- `PLAN_EMPTY`
- `PLAN_TOO_LARGE`
- `PLAN_DUPLICATE_STEP_ID`
- `PLAN_OPERATION_UNSUPPORTED`
- `PLAN_ARGUMENTS_INVALID`
- `PLAN_FILE_NOT_FOUND`
- `PLAN_PREVIEW_MISMATCH`
- `PLAN_PREVIEW_HASH_REQUIRED`
- `PLAN_STEP_FAILED`
- `PLAN_NO_FINAL_CHANGES`
- `PLAN_TESTS_FAILED`
- `PLAN_DATABASE_FAILED`
- `PLAN_NOT_FOUND`
- `PLAN_ALREADY_ROLLED_BACK`
- `PLAN_ROLLBACK_FAILED`
- `PLAN_RECOVERY_REQUIRED`
- `PLAN_STATE_INVALID`
- `PLAN_MANIFEST_INVALID`
- `PLAN_RECOVERY_CONFLICT`
- `ROLLBACK_SELECTOR_CONFLICT`
- `INTERNAL_ERROR`

## Exit Codes

SurePython keeps system exit codes separate from JSON:

- `0`: success
- `2`: refusal or usage error
- `3`: tests failed
- `4`: security or hash mismatch
- `5`: internal error

## `capabilities` JSON

`surepython capabilities --format json` returns:

```json
{
  "protocol_schema_version": "1.0",
  "capabilities_schema_version": "1.0",
  "operations": [],
  "commands": []
}
```

Each operation declares:

- `name`
- `description`
- `status`
- `targets`
- `required_arguments`
- `optional_arguments`
- `supports_dry_run`
- `supports_tests`
- `supports_logging`
- `supports_rollback`
- `supported_formats`
- `possible_error_codes`

Each command declares:

- `name`
- `description`
- `required_arguments`
- `optional_arguments`
- `selectors`
- `mutually_exclusive_selectors`
- `supported_formats`
- `possible_error_codes`
- `supported_parameter_kinds`
- `unsupported_parameter_kinds`
- `status`

The current supported operations now include `add-import`, which is a top-level module edit that adds exactly one explicit import statement with one binding.
The current supported operations also include `remove-docstring`, which removes exactly one exact docstring from a supported module, class, function, or method after verifying the expected logical docstring text.
The current supported operations also include `remove-import`, which removes exactly one explicit module-level import statement after verifying the expected statement.
The current supported operations also include `add-decorator`, which adds exactly one explicit decorator expression to one supported function, method, or class.
The current supported operations also include `remove-return-type`, which removes exactly one explicit return annotation after verifying the expected annotation exactly.
The current supported operations also include `remove-parameter-type`, which removes exactly one explicit parameter annotation after verifying the expected annotation exactly.
The current supported commands also include `plan`, which previews, applies, rolls back, or recovers a transactional plan composed only of supported atomic operations.

## Logging And Rollback

- Real operations with `--db` expose an `operation_id`
- Dry-runs return `operation_id: null`
- Rollback responses expose both the source operation and the rollback log id
- Rollback responses also expose a `selector` object with `type` and `value`
- Parameter annotation responses expose the selected `parameter` name in `target`
- Docstring removal responses expose the expected docstring text, removed docstring text, and target kind in `target`
- Return annotation removal responses expose both the expected annotation and the removed annotation in `target`
- Parameter annotation removal responses expose both the expected annotation and the removed annotation in `target`
- Import insertion responses expose the selected `binding` name and exact `statement` in `target`
- Import removal responses expose the expected statement, removed statement, `import_binding`, and match count in `target`
- Decorator insertion responses expose the selected `symbol`, decorator expression, position, and target kind in `target`
- `legacy/unverifiable` records are refused without writing

## Transactional Plans

`python -m surepython plan` uses the same protocol envelope as the atomic operations.

Plan responses are built around:

- `preview_hash` to bind `plan apply` to a specific previewed state
- `source_plan_operation_id` and `rollback_plan_operation_id` to link grouped rollback records
- `selector` to describe `--last` or `--id`
- `plan_schema_version` in the plan file
- `protocol_schema_version` still equal to `"1.0"`

Plan commands are required to keep `ok`, `status`, `error`, `result`, and `meta` deterministic and JSON-only when `--format json` is requested.

Phase 3.1 tightens the plan protocol further:

- `plan preview`, `plan apply`, `plan rollback`, and `plan recover` are guarded by the project mutation lock
- `PROJECT_MUTATION_LOCKED` means another process is mutating the same project
- `PLAN_STATE_INVALID` means the manifest state transition is not allowed
- `PLAN_MANIFEST_INVALID` means the manifest payload is malformed or its checksum does not match
- `PLAN_RECOVERY_CONFLICT` means more than one incomplete manifest was found for the same project
- `recovered` and `noop` may appear in plan recovery responses

These are still part of the `1.0` root envelope; the protocol schema version does not change.

## Text Compatibility

Text output remains the default for all supported operations. JSON must be explicitly requested with `--format json`.

