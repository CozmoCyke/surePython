# SurePython Phase 3.1 Before/After Report

## Before

- Mutating work relied on Git cleanliness and existing transactional logic, but there was no explicit project mutation lock.
- Manifest validation was weaker and less explicit about malformed or conflicting recovery state.
- Fault handling existed conceptually, but there was no dedicated hardening pass for crash checkpoints.
- Concurrent writers could not be stated as a first-class refusal mode in the public contract.

## After

- Mutating commands are serialized per project by an OS-backed lock.
- Transaction manifests carry schema and checksum validation.
- Invalid, tampered, or conflicting manifest state fails closed with explicit error codes.
- Recovery can distinguish legacy-but-valid manifests from invalid ones.
- Fault injection makes crash-safety and recovery behavior observable in tests.

## What did not change

- The public protocol schema version remains `1.0`.
- The capability surface remains the same public style.
- The phase does not add a new codemod or a new user-facing tag.
- Byte-exact restoration remains the goal for file mutations.

## Validation result

- Full suite: `292 passed`
- No push performed
- No tag created
- Worktree remains the only place where the hardening is represented before commit

## Bottom line

Phase 3.1 turns transactional plans from "works in the happy path" into "fails closed, recovers deterministically, and refuses concurrency hazards."
