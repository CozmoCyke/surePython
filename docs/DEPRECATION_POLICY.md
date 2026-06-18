# Deprecation Policy

SurePython does not silently remove a public capability.

Deprecation follows three steps:

1. announce the deprecation in docs and release notes
2. keep the feature working for a compatibility window
3. remove it only in a later major version with a migration note

## Machine-Readable Warnings

If a public command or option needs a warning, the warning must be carried in JSON instead of being hidden in free-form stdout.

Example:

```json
{
  "meta": {
    "warnings": [
      {
        "code": "DEPRECATED_OPTION",
        "message": "Example warning text",
        "removal_version": "2.0"
      }
    ]
  }
}
```

Warnings are a policy, not a promise that every future warning mechanism already exists.

