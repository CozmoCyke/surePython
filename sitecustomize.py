from __future__ import annotations

import sys
from pathlib import Path


def _add_local_deps() -> None:
    deps = Path(__file__).resolve().parent / ".vendor3"
    if deps.exists():
        deps_path = str(deps)
        if deps_path not in sys.path:
            sys.path.insert(0, deps_path)


_add_local_deps()
