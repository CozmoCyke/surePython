# Distribution Security

SurePython packages are security-sensitive because they define what agents can install and run.

## Principles

- ship only the code and contract data required for the public CLI
- keep release artifacts free of tests, caches, and repository-only CI files
- verify that packaged resources are read from the installed package, not from the checkout
- require clean installation and clean uninstall
- treat the release validator as part of the security boundary

## What The Validator Checks

- wheel and sdist contents
- runtime import path
- CLI availability after install
- packaged contract resources
- uninstall removal

## What It Does Not Do

- it does not widen the supported edit set
- it does not replace the public contract freeze
- it does not relax rollback or hash checks
- it does not create a release tag

If the artifact validation fails, the distribution is not safe to publish yet.
