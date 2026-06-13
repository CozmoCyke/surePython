# SurePython JSON Protocol

This document defines the machine-readable contract used by SurePython phase 2.1.

## Versioning

- `protocol_schema_version`: `"1.0"`
- `capabilities_schema_version`: `"1.0"` for `surepython capabilities --format json`

The JSON protocol is stable for the commands supported in this phase:

- `capabilities`
- `add-docstring`
- `add-return-type`
- `rollback`

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
- `status`: one of `preview`, `applied`, `tested`, `failed`, `rolled_back`, or `refused`
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
- `OPERATION_ID_REQUIRED`
- `OPERATION_ID_INVALID`
- `OPERATION_NOT_FOUND`
- `ROLLBACK_SELECTOR_CONFLICT`
- `ROLLBACK_ALREADY_APPLIED`
- `ROLLBACK_RECORD_NOT_ALLOWED`
- `PROJECT_MISMATCH`
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
- `status`

## Logging And Rollback

- Real operations with `--db` expose an `operation_id`
- Dry-runs return `operation_id: null`
- Rollback responses expose both the source operation and the rollback log id
- Rollback responses also expose a `selector` object with `type` and `value`
- `legacy/unverifiable` records are refused without writing

## Text Compatibility

Text output remains the default for all supported operations. JSON must be explicitly requested with `--format json`.

