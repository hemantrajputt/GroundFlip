"""A deliberately small, non-evaluating JSONPath subset.

Supported forms are ``$``, ``$.field``, ``$['field']``, and ``$[0]``. Wildcards,
filters, script expressions, and recursive descent are rejected.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from .models import InterventionError

_TOKEN = re.compile(
    r"(?:\.([A-Za-z_][A-Za-z0-9_-]*))"
    r"|(?:\[['\"]([^'\"]+)['\"]\])"
    r"|(?:\[(0|[1-9][0-9]*)\])"
)
_MISSING = object()


def parse(path: str) -> tuple[str | int, ...]:
    if not isinstance(path, str) or not path.startswith("$"):
        raise InterventionError(f"Path must start with '$': {path!r}")
    if path == "$":
        return ()
    tokens: list[str | int] = []
    position = 1
    while position < len(path):
        match = _TOKEN.match(path, position)
        if not match:
            raise InterventionError(f"Unsupported JSONPath syntax at offset {position}: {path!r}")
        dotted, quoted, index = match.groups()
        tokens.append(int(index) if index is not None else (dotted or quoted))
        position = match.end()
    return tuple(tokens)


def get(document: Any, path: str, default: Any = _MISSING) -> Any:
    current = document
    try:
        for token in parse(path):
            if isinstance(token, int):
                if not isinstance(current, list):
                    raise TypeError
                current = current[token]
            else:
                if not isinstance(current, dict):
                    raise TypeError
                current = current[token]
        return current
    except (KeyError, IndexError, TypeError):
        if default is not _MISSING:
            return default
        raise InterventionError(f"Path does not exist: {path}") from None


def _parent(document: Any, path: str) -> tuple[Any, str | int]:
    tokens = parse(path)
    if not tokens:
        raise InterventionError("Replacing or deleting the document root is not supported")
    current = document
    for token in tokens[:-1]:
        if isinstance(token, int):
            if not isinstance(current, list) or token >= len(current):
                raise InterventionError(f"Path does not exist: {path}")
        elif not isinstance(current, dict) or token not in current:
            raise InterventionError(f"Path does not exist: {path}")
        current = current[token]
    return current, tokens[-1]


def set_value(document: Any, path: str, value: Any) -> None:
    parent, token = _parent(document, path)
    if isinstance(token, int):
        if not isinstance(parent, list) or token >= len(parent):
            raise InterventionError(f"Path does not exist: {path}")
    elif not isinstance(parent, dict) or token not in parent:
        raise InterventionError(f"Path does not exist: {path}")
    parent[token] = value


def delete(document: Any, path: str) -> None:
    parent, token = _parent(document, path)
    if isinstance(token, int):
        if not isinstance(parent, list) or token >= len(parent):
            raise InterventionError(f"Path does not exist: {path}")
        del parent[token]
    else:
        if not isinstance(parent, dict) or token not in parent:
            raise InterventionError(f"Path does not exist: {path}")
        del parent[token]


def flatten_scalars(document: Any, prefix: str = "$") -> Iterable[tuple[str, Any]]:
    if isinstance(document, dict):
        for key in sorted(document):
            safe = bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", str(key)))
            child = f"{prefix}.{key}" if safe else f"{prefix}[{key!r}]"
            yield from flatten_scalars(document[key], child)
    elif isinstance(document, list):
        for index, item in enumerate(document):
            yield from flatten_scalars(item, f"{prefix}[{index}]")
    else:
        yield prefix, document
