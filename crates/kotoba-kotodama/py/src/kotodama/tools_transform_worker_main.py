"""Generic-primitive worker for com.etzhayyim.tools.transform.* (ADR-2605082000 §2 follow-up).

Per-row declarative transform. Bridges fetched arrays (e.g. http.fetch +
json.extract output) and downstream sql.exec INSERT rows that need
restructured fields, without per-actor Python code.

Mapping grammar (defensive subset; no eval, no JSONPath/JMESPath):

    string  "$.message.items[0]"     → dotted-path lookup (same grammar
                                       as com.etzhayyim.tools.json.extract)
    {const: <any>}                   → literal constant
    {fmt:   "prefix-{a.b}-suffix"}   → format with {path} substituted
                                       from the input row
    {path: "$.x", default: <any>}    → path with fallback

`defaults` is applied first; `mapping` overlays.
"""

from __future__ import annotations

import re
from typing import Any

# Reuse the json.extract path grammar.
from kotodama.tools_json_worker_main import _parse_path, _walk

_PATH_RE = re.compile(r"\A\$\.(.+)\Z")
_FMT_RE = re.compile(r"\{([^{}]+)\}")


def _strip_dollar(p: str) -> str:
    m = _PATH_RE.match(p)
    return m.group(1) if m else p


def _resolve_spec(spec: Any, row: Any) -> Any:
    """Apply a single mapping spec against a row. Returns the resolved value."""
    if isinstance(spec, str):
        # Treat as path. Bare strings without `$.` prefix are also paths
        # (allows `"DOI"` as shorthand for `"$.DOI"`).
        path = _strip_dollar(spec)
        try:
            tokens = _parse_path(path)
        except ValueError:
            return None
        return _walk(row, tokens)
    if isinstance(spec, dict):
        if "const" in spec:
            return spec["const"]
        if "fmt" in spec:
            template = str(spec["fmt"])
            def _sub(m: re.Match) -> str:
                inner = m.group(1)
                try:
                    tokens = _parse_path(_strip_dollar(inner))
                except ValueError:
                    return ""
                v = _walk(row, tokens)
                return "" if v is None else str(v)
            return _FMT_RE.sub(_sub, template)
        if "path" in spec:
            path = _strip_dollar(str(spec["path"]))
            try:
                tokens = _parse_path(path)
            except ValueError:
                return spec.get("default")
            v = _walk(row, tokens)
            return spec.get("default") if v is None else v
    return None


async def task_transform_map(
    *,
    input: Any | None = None,  # noqa: A002 — matches lexicon field name
    mapping: dict[str, Any] | None = None,
    defaults: dict[str, Any] | None = None,
    **_ignored: Any,
) -> dict[str, Any]:
    """Apply the mapping to every input row and return the transformed list."""
    if input is None or mapping is None:
        return {"error": "com.etzhayyim.tools.transform.map: 'input' and 'mapping' are required"}
    if not isinstance(input, list):
        return {"error": "input must be an array"}
    if not isinstance(mapping, dict):
        return {"error": "mapping must be an object"}

    out_rows: list[dict[str, Any]] = []
    skipped = 0
    base = dict(defaults) if isinstance(defaults, dict) else {}
    for row in input:
        if not isinstance(row, dict):
            skipped += 1
            continue
        out: dict[str, Any] = dict(base)
        for out_key, spec in mapping.items():
            out[out_key] = _resolve_spec(spec, row)
        out_rows.append(out)

    return {"rows": out_rows, "rowCount": len(out_rows), "skipped": skipped}
