from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:  # pragma: no cover - script bootstrap
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

import tools.check_release as check_release


ROOT = Path(__file__).resolve().parents[1]


def _select_artifact(dist_dir: Path, kind: str) -> Path:
    patterns = {
        "wheel": "*.whl",
        "sdist": "*.tar.gz",
    }
    matches = sorted(path for path in dist_dir.glob(patterns[kind]) if path.is_file())
    if not matches:
        raise RuntimeError(f"No {kind} artifact found in {dist_dir}")
    if len(matches) > 1:
        names = [path.name for path in matches]
        raise RuntimeError(f"Expected exactly one {kind} artifact in {dist_dir}, found {names}")
    return matches[0]


def validate_distribution_install(*, dist_dir: Path, kind: str, label: str | None = None) -> dict[str, object]:
    artifact = _select_artifact(dist_dir, kind)
    check_release._validate_installed_artifact(artifact, label=label or kind)
    return {
        "ok": True,
        "artifact": artifact.name,
        "dist_dir": str(dist_dir),
        "kind": kind,
        "label": label or kind,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate a built SurePython distribution in a fresh virtual environment.")
    parser.add_argument("--dist-dir", default=str(ROOT / "dist"))
    parser.add_argument("--kind", choices=("wheel", "sdist"), required=True)
    parser.add_argument("--label")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = validate_distribution_install(
            dist_dir=Path(args.dist_dir),
            kind=args.kind,
            label=args.label,
        )
    except Exception as exc:  # pragma: no cover - CLI wrapper
        print(f"::error title=SurePython distribution install validation failed::{exc}", file=sys.stderr)
        print(f"DISTRIBUTION_INSTALL_FAILED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI wrapper
    raise SystemExit(main())
