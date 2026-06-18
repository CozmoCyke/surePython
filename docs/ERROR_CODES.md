# Error Codes

The canonical error registry is stored in `contracts/error_registry_v1.json`.

Each error code records:

- `code`
- `category`
- `description`
- `commands`
- `retryable`
- `project_modified`
- `recovery_required`
- `exit_code`

## Public Contract Rule

An error code is public only if:

1. it has a real execution path
2. it is listed in the registry
3. it is tested
4. it is documented

## Example

```json
{
  "code": "PLAN_PREVIEW_HASH_REQUIRED",
  "category": "plan",
  "description": "Plan preview hash required",
  "commands": ["plan"],
  "retryable": false,
  "project_modified": false,
  "recovery_required": false,
  "exit_code": 2
}
```

