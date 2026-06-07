"""Generic-primitive worker for com.etzhayyim.tools.json.* (ADR-2605082000 §2 follow-up).

Safe dotted-path JSON navigator. Bridges `http.fetch` body strings and
downstream nodes that need a sub-tree. No eval / JSONPath / JMESPath —
defensive subset only.

Path grammar:
  a.b.c       — walk objects (dict.get)
  a.b[2].c    — walk list index
  a.*         — flatten an object's values into a list
                (mostly useful when the values are themselves dicts and
                the consumer wants the union)
  empty path  — return the parsed JSON verbatim
"""

from __future__ import annotations

import json as _json
import re
from typing import Any

# Token splitter: dot-separated, optional [index] tail.
_TOKEN_RE = re.compile(r"([A-Za-z0-9_\-\*]+)(\[\d+\])?")
_INDEX_RE = re.compile(r"\[(\d+)\]")


def _parse_path(path: str) -> list[tuple[str, list[int]]]:
    """Split `a.b[2].c` → [('a', []), ('b', [2]), ('c', [])]."""
    if not path:
        return []
    out: list[tuple[str, list[int]]] = []
    for segment in path.split("."):
        m = _TOKEN_RE.fullmatch(segment) or re.match(r"^([A-Za-z0-9_\-\*]+)((?:\[\d+\])*)$", segment)
        if not m:
            raise ValueError(f"invalid path segment {segment!r}")
        name = m.group(1)
        tail = segment[len(name):]
        idx = [int(g) for g in _INDEX_RE.findall(tail)]
        out.append((name, idx))
    return out


def _walk(obj: Any, tokens: list[tuple[str, list[int]]]) -> Any:
    cur: Any = obj
    for name, indices in tokens:
        if cur is None:
            return None
        if name == "*":
            if isinstance(cur, dict):
                cur = list(cur.values())
            elif isinstance(cur, list):
                pass  # already a list
            else:
                return None
        else:
            if isinstance(cur, dict):
                cur = cur.get(name)
            else:
                return None
        for i in indices:
            if not isinstance(cur, list) or i >= len(cur) or i < 0:
                return None
            cur = cur[i]
    return cur


async def task_json_extract(
    *,
    json: Any | None = None,
    path: str = "",
    default: Any = None,
    **_ignored: Any,
) -> dict[str, Any]:
    """Extract a sub-tree by safe dotted path. Returns ``{"value": ...}``."""
    if json is None:
        return {"error": "com.etzhayyim.tools.json.extract: 'json' is required"}
    parsed: Any
    if isinstance(json, str):
        try:
            parsed = _json.loads(json)
        except _json.JSONDecodeError as exc:
            return {"error": f"json.extract: invalid JSON — {exc}"}
    else:
        parsed = json
    try:
        tokens = _parse_path(path)
    except ValueError as exc:
        return {"error": str(exc)}
    value = _walk(parsed, tokens)
    if value is None and default is not None:
        return {"value": default}
    return {"value": value}
