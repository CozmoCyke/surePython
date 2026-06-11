from __future__ import annotations

import ast
from dataclasses import dataclass


class ParserSyntaxError(SyntaxError):
    pass


@dataclass(frozen=True)
class Module:
    code: str


def parse_module(source: str) -> Module:
    try:
        ast.parse(source)
    except SyntaxError as exc:  # pragma: no cover - validation shim
        raise ParserSyntaxError(str(exc)) from exc
    return Module(code=source)

