# SurePython Phase 1 Spec

## Goal

SurePython v0.1 is a local CLI that authorizes only controlled Python micro-modifications.

## Commands

- `scan`
- `add-docstring`
- `diff`
- `log`

## Safety invariants

1. Modify only one file per operation.
2. Modify only one symbol per operation.
3. Refuse modification if git status is not clean.
4. Refuse modification outside the authorized project root.
5. Refuse to replace an existing docstring.
6. Refuse files that cannot be parsed by LibCST.
7. Always show git diff after modification.
8. Always journal the operation.
9. Never perform global rewrites.
10. Never make creative corrections.

## First use case

Add a skeleton docstring only if the target function or method has no docstring.

Skeleton:

```python
"""TODO: Document this function."""
```

