# Plan Schema v1

This document defines the JSON shape consumed by `python -m surepython plan preview`.
The schema is intentionally minimal so the same plan can be previewed, applied, rolled back, or recovered without rewriting the plan file itself.

## Top Level

```json
{
  "plan_schema_version": "1.0",
  "name": "optional human label",
  "description": "optional explanation",
  "client_plan_id": "optional external id",
  "metadata": {},
  "steps": []
}
```

## Step Shape

```json
{
  "id": "step-1",
  "operation": "add-docstring",
  "file": "module_a.py",
  "arguments": {}
}
```

Rules:

- `id` must be unique within the plan
- `operation` must be one of the supported SurePython atomic operations
- `file` must be relative to the project root
- `arguments` must match the exact contract for the selected operation
- file paths must stay relative to the project root
- step ids must be unique
- the plan must contain at least one step and at most the supported maximum

## Example

```json
{
  "plan_schema_version": "1.0",
  "name": "sample transactional plan",
  "steps": [
    {
      "id": "docstring-step",
      "operation": "add-docstring",
      "file": "module_a.py",
      "arguments": {
        "symbol": "Service.greet",
        "docstring": "Greet a user."
      }
    },
    {
      "id": "return-step",
      "operation": "add-return-type",
      "file": "module_b.py",
      "arguments": {
        "symbol": "load_user",
        "annotation": "str | None"
      }
    }
  ]
}
```

`plan apply` refuses unless the caller supplies the exact `preview_hash` produced by `plan preview`. That contract keeps plan application tied to the specific previewed state and prevents accidental application of a drifted or stale plan.
