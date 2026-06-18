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

Supported write operations currently include add-docstring, add-return-type, remove-return-type, add-parameter-type, add-import, and remove-import.
Supported write operations currently also include add-decorator.
Supported write operations currently also include remove-parameter-type.
Supported write operations currently also include remove-decorator.
Supported write operations currently also include remove-docstring.

The public contract snapshots live under `contracts/` and are validated by `tools/check_contracts.py`.
Before changing any public CLI surface, error code, JSON envelope, plan schema, or SQLite schema, compare the code to the frozen contract.

For release work, keep packaging changes additive and validate artifacts with `tools/check_release.py` before recommending a public tag.

When no supported operation matches:

1. State that the change is outside the current capability set.
2. Use normal Codex editing.
3. Record the fallback and its reason in the relevant phase report.

Never claim that a direct edit was secured by SurePython.
