# SurePython Phase 2.10 Pre-Merge Review

## Scope

- Branch: `feature/phase-2.10-remove-docstring`
- Review target SHA: `2edee5ceb18f48a1c83e9fb407b86e0eecf0925b`
- Subject: `Add safe explicit docstring removal`
- Baseline `main` / `origin/main`: `5fc8ec338ed418858ced0c4f63b129fb0889f870`
- Public tag: `v0.12.0-public-preview`

## What Was Reviewed

The review inspected the Phase 2.10 delta in:

- `surepython/codemods.py`
- `surepython/rollback.py`
- `surepython/cli.py`
- `surepython/datasette_log.py`
- `surepython/protocol.py`
- `surepython/capabilities.py`
- `tests/test_remove_docstring.py`
- `tests/test_capabilities.py`
- `docs/PROTOCOL_JSON.md`
- product and tutorial documentation

## Review Findings

### Defect 1: add/remove docstring did not restore LF byte-for-byte

The first review pass showed that a document round-trip could drift on LF-only files because `add_docstring` still wrote through text normalization. That meant the add/remove cycle was not byte-stable on some inputs.

#### Correction applied

- `add_docstring` now reads source bytes, decodes once, and writes back with `write_bytes`.
- A newline normalization helper now preserves the original newline style when rebuilding text.
- `remove_docstring` uses the same newline normalization path before encoding.

This restores the exact original bytes for the add/remove cycle, including LF-only files.

### Defect 2: `DOCSTRING_REPRESENTATION_UNSUPPORTED` was publicly advertised too broadly

The review also removed `DOCSTRING_REPRESENTATION_UNSUPPORTED` from the public capability and protocol surfaces for `remove-docstring`.

#### Correction applied

- Removed it from `surepython/capabilities.py` for the public remove-docstring contract.
- Removed it from `surepython/protocol.py` exit-code exposure.
- Removed it from `docs/PROTOCOL_JSON.md`.
- Kept the internal defensive branch in the implementation, but not as a public contract code.

## Real Definition Of A Docstring

SurePython Phase 2.10 treats a docstring as:

- the first effective statement in a module, class, function, or method body;
- a string literal only, not an f-string, bytes literal, or arbitrary expression;
- logically compared by its decoded string value, not by its quote syntax;
- removable only when it is genuinely the docstring target for the selected symbol.

## Logical Comparison Rule

The expected text is compared against the logical docstring value after decoding, not against raw source spelling.

That means:

- single quotes, double quotes, and triple quotes are accepted when they represent a valid docstring;
- multiline docstrings are compared by their logical content;
- a mismatch yields `DOCSTRING_MISMATCH`;
- no later string literal is removed accidentally;
- if the string is not the first effective instruction, SurePython refuses with `DOCSTRING_NOT_FOUND`.

## Supported And Refused Representations

### Supported

- regular docstring string literals using supported quote forms
- multiline docstrings with clear logical text
- docstrings on modules, classes, functions, and methods
- docstring-only bodies where `pass` must be inserted for function/class bodies

### Refused

- f-strings
- bytes literals
- non-docstring strings that appear after another instruction
- inline suites that are not safely representable
- unsupported target shapes

`DOCSTRING_REPRESENTATION_UNSUPPORTED` is no longer a public contract code in this phase.

## Targeting And Scope

The implementation and tests confirm:

- module targets are handled explicitly
- class targets are handled explicitly
- function targets are handled explicitly
- method targets are handled explicitly
- later string literals remain untouched
- decorators, annotations, parameters, return types, bases, metaclasses, imports, and body content remain unchanged

## `pass` Insertion

- If a function or class body contains only the removed docstring, `pass` is inserted explicitly.
- If a module docstring is removed, no `pass` is inserted.

## Inline Suites

Inline suites are rejected by the current contract when they cannot be represented safely as a supported removal operation.

## Comments

Inline and standalone comments are preserved and do not disappear silently.

## Multiline Docstrings

Multiline docstrings are compared and removed using a clear logical-text rule. The tests now cover a multiline example and verify the removed logical text exactly.

## Shebang, Encoding, And `__future__`

The implementation preserves:

- shebang lines
- encoding comments
- `from __future__` imports
- final newline presence or absence
- BOM presence when present

## Protocol, Capabilities, And Errors

The review confirmed that:

- protocol schema remains `1.0`
- capabilities schema remains `1.0`
- stdout stays structured for JSON mode
- the documented error set matches the real behavior
- `DOCSTRING_REQUIRED`
- `DOCSTRING_NOT_FOUND`
- `DOCSTRING_MISMATCH`
- `DOCSTRING_TARGET_UNSUPPORTED`
- `DOCSTRING_INLINE_SUITE_UNSUPPORTED`

No new public `DOCSTRING_AMBIGUOUS` code was introduced.

## SQLite Compatibility

SQLite logging remains:

- additive
- idempotent
- compatible with older bases
- safe for the existing rollback journal

The review did not require a destructive migration.

## Rollback

The rollback path remains valid for:

- `rollback --last`
- `rollback --id <operation_id>`

The reviewed smoke confirmed the rollback of a docstring removal that inserted `pass` restores the original bytes exactly.

## Composition

The reviewed smoke and tests confirm composition with:

- decorators
- annotations
- imports
- typed class methods

Only the docstring changes; the rest of the definition is preserved.

## Smokes

Validated smoke cases:

1. Decorated and typed class method with real docstring removal.
2. Function/class body reduced to `pass` when the docstring was the only statement.
3. A later string literal that is not a docstring, which correctly produces `DOCSTRING_NOT_FOUND`.

## Self-Hosting

This phase remained a codebase review and correction phase. The self-hosting evidence still points to selective, controlled use of SurePython for operations that it already supports.

## Final Validation

- Full suite: `259 passed`
- Targeted review tests: `20 passed`
- `surepython capabilities --format json`: OK
- `surepython scan surepython --format json`: OK
- `surepython diff`: clean
- `git diff --check`: clean
- `git status --short`: clean after commit

## Residual Risks

- Inline-suite handling remains intentionally conservative.
- The internal defensive representation branch exists, but the public contract no longer advertises it.
- No broad behavior beyond Phase 2.10 was changed.

## Recommendation

**Ready for transfer.**

The review found one real byte-stability defect and one public-contract overexposure, and both were corrected. The current implementation is consistent with the Phase 2.10 contract, the test suite is green, and the worktree is ready to be committed as the review/correction commit before merge.
