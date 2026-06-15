# SurePython Phase 2.7 Architecture Audit

## Scope

Phase 2.7 adds a new compare-and-remove codemod:

- `remove-parameter-type`

The goal is to remove exactly one explicit annotation from exactly one parameter, only after verifying the parameter name and the expected annotation.

## Existing Building Blocks

The current implementation already provides:

- target resolution for qualified function and method names
- parameter kind detection
- LibCST-based annotation insertion and removal patterns
- byte-preserving rollback for logged operations
- SQLite logging with additive schema extension
- JSON protocol responses with stable error codes

Relevant code paths:

- `surepython/codemods.py`
- `surepython/rollback.py`
- `surepython/datasette_log.py`
- `surepython/cli.py`
- `surepython/capabilities.py`
- `surepython/protocol.py`

## How to Identify One Unique Parameter

The safest path is:

1. Resolve the exact qualified function or method symbol with the existing scanner.
2. Parse the target function with AST and LibCST.
3. Locate the parameter by name in one of:
   - positional-only parameters
   - positional-or-keyword parameters
   - keyword-only parameters
4. Reject variadic parameters:
   - `*args`
   - `**kwargs`

Python signatures do not allow duplicate parameter names inside a valid function definition, so an explicit parameter-ambiguity state is not required for a correct signature. If a symbol lookup is ambiguous at the function level, the existing `TARGET_AMBIGUOUS` path should remain responsible for that refusal.

## Distinguishing Parameter Categories

The current `add-parameter-type` implementation already distinguishes:

- positional-only
- positional-or-keyword
- keyword-only
- variadic positional
- variadic keyword

Phase 2.7 should reuse that categorization logic so the new remove operation stays symmetric with the add operation.

## How to Check the Current Annotation

The new remove operation should:

1. Load the current annotation from the AST / LibCST node.
2. Parse the expected annotation string into a LibCST expression.
3. Compare the two structurally.
4. Refuse when they differ.

This compare-and-remove rule prevents the codemod from deleting an annotation just because the parameter is annotated.

## How to Remove Only the Annotation

The transformation should update only the parameter annotation field and leave the rest untouched:

- parameter order stays the same
- defaults stay the same
- `/` and `*` markers stay the same
- surrounding annotations stay the same
- decorators stay the same
- return annotations stay the same
- function bodies stay the same
- comments stay the same

The same byte-exact strategy used by rollback should be reused for post-edit reconstruction and rollback validation.

## How to Preserve Defaults, `/`, and `*`

LibCST should update the `Param.annotation` field only. The rest of the signature should be left untouched so:

- default expressions do not reformat
- positional-only markers remain present
- keyword-only markers remain present
- `self` and `cls` behave like any other explicit parameter names when explicitly targeted

## Why `*args` and `**kwargs` Stay Rejected

Variadic parameters do not represent a single ordinary parameter annotation removal target in this phase.

The product contract remains symmetric with `add-parameter-type`:

- ordinary parameters are supported
- variadic parameters are rejected with `PARAMETER_KIND_UNSUPPORTED`

This keeps the operation narrow and predictable.

## Expected Annotation Comparison

Expected annotations should be parsed with the same centralized annotation validation approach already used elsewhere.

The comparison should be structural, not textual-only:

- whitespace differences do not matter when the LibCST tree is the same
- semantic equivalence is not inferred
- imports are not resolved
- aliases are not resolved
- quoted and unquoted forms are not treated as interchangeable unless their trees are truly identical

## Logging the Removed Annotation

The SQLite record should store:

- the target file
- the qualified symbol
- the parameter name
- the parameter kind
- the expected annotation
- the removed annotation
- the before and after SHA-256 values
- the project root
- the status and test outcome

This gives rollback enough data to restore the original bytes safely.

## Byte-Exact Rollback

Rollback should mirror the existing byte-exact design:

1. confirm the logged operation is compatible
2. confirm the current file hash matches the logged `after_sha256`
3. restore the original annotation using the logged annotation text
4. verify the restored bytes hash to `before_sha256`
5. refuse if the restored bytes cannot be proven exact

## Generalization

The Phase 2.7 design should make compare-and-remove reusable for future removal operations:

- exact target
- exact existing value
- exact expected value
- byte-exact logging
- byte-exact rollback

## Recommendation

Proceed with a narrow implementation:

- one new codemod
- one new CLI command
- additive SQLite fields only
- structural annotation comparison
- reuse of current rollback infrastructure
- no import resolution
- no semantic equivalence
