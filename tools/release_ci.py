from __future__ import annotations

import subprocess
import sys
from pathlib import Path

if __package__ in {None, ""}:  # pragma: no cover - script bootstrap
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    completed = subprocess.run(
        [sys.executable, "tools/check_release.py", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    if completed.returncode != 0:
        stderr = [line for line in completed.stderr.strip().splitlines() if line and not line.startswith("::error")]
        summary = stderr[-1] if stderr else "release validation failed"
        print(f"::error title=SurePython release validation failed::{summary}")
    return completed.returncode


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
