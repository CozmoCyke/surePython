# Release Process

SurePython releases are validated, not guessed.

## Release Sequence

1. Freeze the code and contracts on a clean branch.
2. Build wheel and sdist artifacts.
3. Run `twine check`.
4. Validate artifact contents.
5. Install the wheel and sdist into fresh virtual environments.
6. Run runtime smoke tests.
7. Confirm uninstall removes the importable package.
8. Record the result in a phase report.
9. Create an annotated public tag only after the release candidate is proven.

## Release Candidate Rule

If the validator finds a missing file, forbidden file, import failure, or uninstall failure, the release candidate is not ready.

The fix should be applied in source, retested, and documented before any tag is created.
