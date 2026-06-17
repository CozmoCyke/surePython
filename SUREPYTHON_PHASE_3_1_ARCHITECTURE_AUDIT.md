# SurePython Phase 3.1 Architecture Audit

## Scope

Phase 3.1 hardens transactional plans without adding a new codemod or a new public workflow. The change set focuses on concurrency control, manifest integrity, and recovery safety.

## Current architecture

- Mutating commands now acquire a project-scoped OS lock before touching files or SQLite.
- The lock metadata is stored outside the Git tree, so it does not pollute diffs.
- Transactional plan state is tracked through an on-disk manifest with a schema version and checksum.
- Recovery distinguishes between incomplete manifests, invalid manifests, and concurrent recovery conflicts.
- Fault injection hooks exist for crash-safety testing during apply, rollback, and recovery.

## Reused logic

- Existing protocol and capabilities plumbing remains the public contract surface.
- Existing Git cleanliness checks and byte-exact file restoration remain in place.
- Existing plan rollback and recovery machinery are reused instead of being replaced.

## New hardening concerns

- Prevent concurrent mutations from two processes in the same project.
- Reject malformed or tampered transaction manifests.
- Preserve compatibility with legacy manifests that predate schema/checksum fields.
- Surface explicit recovery conflicts instead of silently guessing which manifest to trust.

## Compatibility notes

- Legacy manifests remain readable when their structure is still minimally valid.
- Older plan records remain rollbackable when the recorded source data is sufficient.
- The public protocol schema version remains `1.0`.
- The hardening work does not introduce a new codemod or a new tag.

## Recommended implementation boundary

The minimal safe boundary is:

- lock before mutation;
- validate manifests before apply or recovery;
- fail closed on malformed, conflicting, or tampered state;
- preserve byte-exact file restoration and existing plan semantics.
