from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def _first_failure_summary(junit_path: Path) -> str | None:
    if not junit_path.exists():
        return None
    try:
        root = ET.parse(junit_path).getroot()
    except ET.ParseError:
        return None
    for testcase in root.iter("testcase"):
        failure = testcase.find("failure")
        if failure is None:
            failure = testcase.find("error")
        if failure is None:
            continue
        classname = testcase.attrib.get("classname", "")
        name = testcase.attrib.get("name", "")
        message = (failure.attrib.get("message") or (failure.text or "")).strip()
        parts = [part for part in [classname, name, message] if part]
        if parts:
            return " :: ".join(parts)
    return None


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    completed = subprocess.run([sys.executable, "-m", "pytest", *args], check=False)
    if completed.returncode != 0:
        junit_path = None
        for index, arg in enumerate(args):
            if arg == "--junitxml" and index + 1 < len(args):
                junit_path = Path(args[index + 1])
                break
            if arg.startswith("--junitxml="):
                junit_path = Path(arg.split("=", 1)[1])
                break
        summary = _first_failure_summary(junit_path) if junit_path is not None else None
        if summary:
            print(f"::error title=Pytest failure::{summary}")
        else:
            print("::error title=Pytest failure::pytest exited with a non-zero status")
    return completed.returncode


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
