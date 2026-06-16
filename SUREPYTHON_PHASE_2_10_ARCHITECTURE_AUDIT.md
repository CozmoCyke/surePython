# SurePython Phase 2.10 Architecture Audit

## Scope

Phase 2.10 introduces `remove-docstring`, a narrow compare-and-remove operation that deletes exactly one docstring after confirming the expected logical text.

Supported targets:

- module
- class
- function
- method

## Reused Architecture

The phase reuses the same safety stack as the earlier micro-operations:

- `capabilities --format json` for agent discovery
- `scan --format json` for symbol localization
- `--dry-run` before a real edit
- `--test` for optional pytest validation
- `--db` for SQLite logging
- explicit rollback through logged state
- JSON protocol `1.0`

## Required Additions

The implementation needs additive support for docstring removal state:

- expected docstring text
- removed docstring text
- removed docstring source text
- docstring target kind
- exact pre-image bytes for byte-perfect rollback

These fields remain nullable so existing databases stay compatible.

## Compatibility Notes

- Existing `add-docstring` logs remain valid.
- Existing rollback selectors continue to work.
- Legacy databases without the new columns are still readable through additive schema migration.
- Historical records that cannot reconstruct the exact pre-image remain guarded by `LEGACY_UNVERIFIABLE`.

## Rollback Strategy

Rollback for `remove-docstring` is safest when it reuses the logged pre-image bytes. That preserves:

- LF versus CRLF
- UTF-8 BOM presence
- final newline bytes
- any byte-level details already present in the original file

The rollback code must still verify the restored hash against `before_sha256` before writing.

## Public Contract Impact

The new operation should be surfaced in:

- `README.md`
- `docs/TUTORIAL_FR.md`
- `docs/CODEX_INTEGRATION.md`
- `docs/AGENTS_TEMPLATE.md`
- `docs/PROTOCOL_JSON.md`
- `docs/WINDOWS_TROUBLESHOOTING.md`

## Audit Conclusion

The phase is compatible with the existing architecture because it follows the same one-file, one-symbol, proof-before-write model. The only new trust material is the recorded docstring pre-image and the docstring-specific metadata needed for rollback and protocol reporting.
