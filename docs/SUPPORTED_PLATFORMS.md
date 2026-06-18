# Supported Platforms

SurePython Phase 3.3 is validated for:

- Windows 11 with Python 3.12
- Linux with Python 3.12
- macOS with Python 3.12

The release validator also checks that the packaged artifacts install into fresh virtual environments and that the CLI behaves the same after installation.

## Compatibility Expectations

- UTF-8 source files
- LF and CRLF preservation in supported edits
- UTF-8 BOM preservation where present
- clean wheel and sdist contents
- uninstallable packaged installs

The supported platform matrix is conservative. If a platform is not listed here, it is not part of the release promise.
