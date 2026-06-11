from __future__ import annotations

import importlib.util
import inspect
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory


class _MonkeyPatch:
    def __init__(self) -> None:
        self._original_env: dict[str, str | None] = {}

    def setenv(self, name: str, value: str) -> None:
        import os

        if name not in self._original_env:
            self._original_env[name] = os.environ.get(name)
        os.environ[name] = value

    def delenv(self, name: str, raising: bool = True) -> None:
        import os

        if name not in self._original_env:
            self._original_env[name] = os.environ.get(name)
        if name in os.environ:
            del os.environ[name]
        elif raising:
            raise KeyError(name)

    def undo(self) -> None:
        import os

        for name, value in self._original_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_test_function(func):
    parameters = inspect.signature(func).parameters
    kwargs = {}
    temp_dir = None
    monkeypatch = None
    try:
        if "tmp_path" in parameters:
            temp_dir = TemporaryDirectory()
            kwargs["tmp_path"] = Path(temp_dir.name)
        if "monkeypatch" in parameters:
            monkeypatch = _MonkeyPatch()
            kwargs["monkeypatch"] = monkeypatch
        func(**kwargs)
    finally:
        if monkeypatch is not None:
            monkeypatch.undo()
        if temp_dir is not None:
            temp_dir.cleanup()


def main(args: list[str] | None = None) -> int:
    test_root = Path.cwd() / "tests"
    test_files = sorted(test_root.glob("test_*.py"))
    failures = 0
    for file_path in test_files:
        module = _load_module(file_path)
        for name, value in sorted(vars(module).items()):
            if name.startswith("test_") and callable(value):
                try:
                    _run_test_function(value)
                    print(f"{file_path.name}::{name} PASSED")
                except Exception as exc:  # noqa: BLE001
                    failures += 1
                    print(f"{file_path.name}::{name} FAILED: {exc}")
    if failures:
        print(f"{failures} failed")
        return 1
    print(f"{len(test_files)} files passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

