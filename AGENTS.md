# SurePython self-hosting policy

Before editing Python code, query:

`python -m surepython capabilities --format json`

When the intended change matches a supported SurePython operation:

1. Run `surepython scan` and identify the exact qualified symbol.
2. Run the supported operation with `--dry-run --format json`.
3. Parse and inspect the JSON response.
4. Apply with `--test --db`.
5. Record the returned `operation_id`.
6. Do not replace this operation with a direct manual edit.
7. Never bypass a SurePython refusal.

When no supported operation matches:

1. State that the change is outside the current capability set.
2. Use normal Codex editing.
3. Record the fallback and its reason in the Phase 2.2 report.

Never claim that a direct edit was secured by SurePython.
