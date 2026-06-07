"""isaaclab.utils.io — save/load helpers (yaml / pickle / json).

Mirror of `isaaclab.utils.io` (Isaac Lab 1.x). Used for cfg serialization
(YAML), checkpoint restore (pickle), structured logging (JSON), and
arbitrary blob save/load via auto-dispatch.

Public surface:
  - dump_yaml(filename, data, sort_keys=False)
  - load_yaml(filename) → dict
  - dump_pickle(filename, data)
  - load_pickle(filename) → object
  - dump_json(filename, data, indent=2)
  - load_json(filename) → object
  - save_to_dict(filename, data)  — dispatch by extension
  - load_from_dict(filename)      — dispatch by extension

YAML implementation: minimal block-style emitter + indent-based parser
that round-trips the subset Isaac Lab actually uses (string keys; scalar
/ list / nested-dict values). Tuples are emitted as flow lists `[a, b]`
since YAML 1.2 has no tuple type. Loader produces lists (not tuples) —
callers that need tuples should post-process.

Pickle uses stdlib `pickle` (default protocol). JSON uses stdlib `json`.
"""

from __future__ import annotations

import json
import os
import pickle
from typing import Any, Dict


# ────────────────────────────────────────────────────────────────────────────
# YAML — minimal block-style emitter + indent-based parser
# ────────────────────────────────────────────────────────────────────────────


def _yaml_emit_scalar(v: Any) -> str:
    """Format a scalar as a YAML literal."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)  # repr() preserves float precision
    if isinstance(v, str):
        # Quote when needed: empty, starts with special chars, contains
        # YAML-ambiguous tokens, or matches a number/bool literal.
        if not v:
            return '""'
        if v in ("true", "false", "null", "yes", "no", "on", "off"):
            return f'"{v}"'
        if v[0] in " -?:,[]{}\"'#&*!|>%@`":
            return json.dumps(v)
        if any(c in v for c in "\n\t\r#"):
            return json.dumps(v)
        # Plain string is safe.
        return v
    return json.dumps(v)


def _yaml_emit(data: Any, indent: int = 0, indent_step: int = 2,
                sort_keys: bool = False) -> str:
    """Emit YAML for `data`. Block style for dicts + non-trivial lists;
    flow style for short / scalar-only lists."""
    pad = " " * indent

    if data is None or isinstance(data, (bool, int, float, str)):
        return _yaml_emit_scalar(data)

    if isinstance(data, dict):
        if not data:
            return "{}"
        items = sorted(data.items()) if sort_keys else list(data.items())
        lines = []
        for k, v in items:
            key = str(k)
            if isinstance(v, dict):
                if not v:
                    lines.append(f"{pad}{key}: {{}}")
                else:
                    lines.append(f"{pad}{key}:")
                    lines.append(_yaml_emit(v, indent + indent_step,
                                              indent_step, sort_keys))
            elif isinstance(v, (list, tuple)):
                # Decide flow vs block at the value level so block lists
                # go on the next line under `key:`.
                if not v:
                    lines.append(f"{pad}{key}: []")
                elif all(
                    item is None or isinstance(item, (bool, int, float, str))
                    for item in v
                ):
                    flow = (
                        "[" + ", ".join(_yaml_emit_scalar(i) for i in v) + "]"
                    )
                    if len(flow) < 60:
                        lines.append(f"{pad}{key}: {flow}")
                    else:
                        lines.append(f"{pad}{key}:")
                        lines.append(_yaml_emit_list(
                            v, indent + indent_step, indent_step, sort_keys,
                        ))
                else:
                    # Nested / non-scalar items → block list on next line.
                    lines.append(f"{pad}{key}:")
                    lines.append(_yaml_emit_list(
                        v, indent + indent_step, indent_step, sort_keys,
                    ))
            else:
                lines.append(f"{pad}{key}: {_yaml_emit_scalar(v)}")
        return "\n".join(lines)

    if isinstance(data, (list, tuple)):
        return _yaml_emit_list(data, indent, indent_step, sort_keys)

    return _yaml_emit_scalar(data)


def _yaml_emit_list(data: Any, indent: int, indent_step: int,
                     sort_keys: bool) -> str:
    """Emit a list as flow style (`[a, b]`) when all scalar + short;
    block style otherwise."""
    items = list(data)
    if not items:
        return "[]"
    # Flow style when all scalar AND total length < 60 chars.
    flow_safe = all(
        item is None or isinstance(item, (bool, int, float, str))
        for item in items
    )
    if flow_safe:
        flow = "[" + ", ".join(_yaml_emit_scalar(i) for i in items) + "]"
        if len(flow) < 60:
            return flow
    # Block style.
    pad = " " * indent
    out = []
    for item in items:
        if isinstance(item, dict):
            # Render dict on first line after `- `.
            dict_str = _yaml_emit(item, indent + indent_step, indent_step, sort_keys)
            # Strip leading pad so `- ` lines up with first key.
            lines = dict_str.split("\n")
            first = lines[0].lstrip()
            rest = lines[1:]
            out.append(f"{pad}- {first}")
            for r in rest:
                out.append(r)
        elif isinstance(item, (list, tuple)):
            out.append(f"{pad}- {_yaml_emit_list(item, indent + indent_step, indent_step, sort_keys)}")
        else:
            out.append(f"{pad}- {_yaml_emit_scalar(item)}")
    return "\n".join(out)


def dump_yaml(filename: str, data: Any, sort_keys: bool = False) -> None:
    """Write `data` to `filename` in YAML. Creates parent dirs as needed."""
    os.makedirs(os.path.dirname(os.path.abspath(filename)) or ".", exist_ok=True)
    body = _yaml_emit(data, sort_keys=sort_keys)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(body)
        if not body.endswith("\n"):
            f.write("\n")


def _yaml_parse_scalar(s: str) -> Any:
    """Parse a YAML scalar string into a Python value."""
    s = s.strip()
    if not s:
        return ""
    if s == "null" or s == "~":
        return None
    if s == "true":
        return True
    if s == "false":
        return False
    # Quoted string: use JSON parser.
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        if s.startswith('"'):
            return json.loads(s)
        return s[1:-1]
    # Inline list `[a, b, c]` — JSON-style.
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [_yaml_parse_scalar(p) for p in _split_top_level(inner, ",")]
    # Inline dict `{a: 1, b: 2}` — minimal support.
    if s.startswith("{") and s.endswith("}"):
        inner = s[1:-1].strip()
        if not inner:
            return {}
        out = {}
        for part in _split_top_level(inner, ","):
            if ":" not in part:
                continue
            k, v = part.split(":", 1)
            out[k.strip()] = _yaml_parse_scalar(v)
        return out
    # Try int / float.
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    # Plain string.
    return s


def _split_top_level(s: str, sep: str) -> list:
    """Split `s` on `sep` but ignore separators inside brackets / braces /
    quotes."""
    out = []
    cur: list = []
    depth = 0
    in_str = False
    quote_char = None
    for c in s:
        if in_str:
            cur.append(c)
            if c == quote_char and (not cur or cur[-2:-1] != ["\\"]):
                in_str = False
            continue
        if c in ('"', "'"):
            in_str = True
            quote_char = c
            cur.append(c)
            continue
        if c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
        if c == sep and depth == 0:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(c)
    if cur:
        out.append("".join(cur).strip())
    return out


def load_yaml(filename: str) -> Any:
    """Parse YAML file produced by dump_yaml. Subset only — top-level
    must be a dict / list."""
    with open(filename, "r", encoding="utf-8") as f:
        text = f.read()
    return _yaml_parse_block(text)


def _yaml_parse_block(text: str) -> Any:
    """Parse a YAML block — handles dicts (key: value), block lists
    (`- item`), nested via indent."""
    # Tokenize by lines (skip blank + comment lines).
    raw_lines = text.split("\n")
    lines: list = []
    for ln in raw_lines:
        stripped = ln.rstrip()
        if not stripped.strip() or stripped.strip().startswith("#"):
            continue
        lines.append(stripped)
    if not lines:
        return {}
    # Detect top-level structure: dict (key:) or list (- item).
    first = lines[0].lstrip()
    if first.startswith("- "):
        return _parse_list(lines, 0)[0]
    return _parse_dict(lines, 0)[0]


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip())


def _parse_dict(lines: list, start: int) -> tuple:
    """Parse a dict starting at `lines[start]`. Returns (dict, next_idx)."""
    result: Dict[str, Any] = {}
    if start >= len(lines):
        return result, start
    base_indent = _indent_of(lines[start])
    i = start
    while i < len(lines):
        line = lines[i]
        indent = _indent_of(line)
        if indent < base_indent:
            break
        if indent > base_indent:
            i += 1
            continue
        content = line[base_indent:]
        if content.startswith("- "):
            break  # not a dict, caller dispatches
        if ":" not in content:
            i += 1
            continue
        key_part, _, value_part = content.partition(":")
        key = key_part.strip()
        value_str = value_part.strip()
        if not value_str:
            # Nested dict or list on the following lines.
            if i + 1 < len(lines):
                next_indent = _indent_of(lines[i + 1])
                if next_indent > base_indent:
                    nxt_content = lines[i + 1][next_indent:]
                    if nxt_content.startswith("- "):
                        value, i = _parse_list(lines, i + 1)
                        result[key] = value
                        continue
                    value, i = _parse_dict(lines, i + 1)
                    result[key] = value
                    continue
            # No nested content; empty value.
            result[key] = None
            i += 1
            continue
        # Inline scalar / flow list / flow dict.
        result[key] = _yaml_parse_scalar(value_str)
        i += 1
    return result, i


def _parse_list(lines: list, start: int) -> tuple:
    """Parse a block list `- item` lines starting at lines[start]. Returns
    (list, next_idx)."""
    result: list = []
    if start >= len(lines):
        return result, start
    base_indent = _indent_of(lines[start])
    i = start
    while i < len(lines):
        line = lines[i]
        indent = _indent_of(line)
        if indent < base_indent:
            break
        if indent > base_indent:
            i += 1
            continue
        content = line[base_indent:]
        if not content.startswith("- "):
            break
        item_str = content[2:].strip()
        if not item_str:
            # Item is a nested structure on following lines.
            if i + 1 < len(lines):
                next_indent = _indent_of(lines[i + 1])
                if next_indent > base_indent:
                    nxt_content = lines[i + 1][next_indent:]
                    if nxt_content.startswith("- "):
                        nested, i = _parse_list(lines, i + 1)
                    else:
                        nested, i = _parse_dict(lines, i + 1)
                    result.append(nested)
                    continue
            result.append(None)
            i += 1
            continue
        # Inline: scalar / dict-on-first-line / flow.
        # Check if item is a "key: value" pair (inline dict start).
        if ":" in item_str and not item_str.startswith(("[", "{", '"', "'")):
            # Treat as dict starting on this line.
            key_part, _, value_part = item_str.partition(":")
            key = key_part.strip()
            value_str = value_part.strip()
            sub: Dict[str, Any] = {}
            if value_str:
                sub[key] = _yaml_parse_scalar(value_str)
            else:
                sub[key] = None
            # Continue parsing further keys at deeper indent.
            i += 1
            while i < len(lines):
                line = lines[i]
                indent = _indent_of(line)
                if indent <= base_indent:
                    break
                content = line[indent:]
                if content.startswith("- "):
                    break
                if ":" not in content:
                    i += 1
                    continue
                k_part, _, v_part = content.partition(":")
                sub[k_part.strip()] = _yaml_parse_scalar(v_part.strip())
                i += 1
            result.append(sub)
            continue
        result.append(_yaml_parse_scalar(item_str))
        i += 1
    return result, i


# ────────────────────────────────────────────────────────────────────────────
# Pickle
# ────────────────────────────────────────────────────────────────────────────


def dump_pickle(filename: str, data: Any, protocol: int = pickle.DEFAULT_PROTOCOL) -> None:
    """Write `data` to `filename` via pickle. Creates parent dirs."""
    os.makedirs(os.path.dirname(os.path.abspath(filename)) or ".", exist_ok=True)
    with open(filename, "wb") as f:
        pickle.dump(data, f, protocol=protocol)


def load_pickle(filename: str) -> Any:
    """Load pickle file."""
    with open(filename, "rb") as f:
        return pickle.load(f)


# ────────────────────────────────────────────────────────────────────────────
# JSON
# ────────────────────────────────────────────────────────────────────────────


def dump_json(filename: str, data: Any, indent: int = 2,
               sort_keys: bool = False) -> None:
    """Write `data` to `filename` as JSON."""
    os.makedirs(os.path.dirname(os.path.abspath(filename)) or ".", exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, sort_keys=sort_keys)
        f.write("\n")


def load_json(filename: str) -> Any:
    """Load JSON file."""
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)


# ────────────────────────────────────────────────────────────────────────────
# Auto-dispatch by extension
# ────────────────────────────────────────────────────────────────────────────


_DISPATCH_DUMP = {
    ".yaml": dump_yaml,
    ".yml": dump_yaml,
    ".pkl": dump_pickle,
    ".pickle": dump_pickle,
    ".json": dump_json,
}


_DISPATCH_LOAD = {
    ".yaml": load_yaml,
    ".yml": load_yaml,
    ".pkl": load_pickle,
    ".pickle": load_pickle,
    ".json": load_json,
}


def save_to_dict(filename: str, data: Any) -> None:
    """Save `data` to `filename`; format dispatched by extension."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in _DISPATCH_DUMP:
        raise ValueError(
            f"unsupported extension {ext!r}; "
            f"supported: {sorted(_DISPATCH_DUMP.keys())}"
        )
    _DISPATCH_DUMP[ext](filename, data)


def load_from_dict(filename: str) -> Any:
    """Load `filename`; format dispatched by extension."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in _DISPATCH_LOAD:
        raise ValueError(
            f"unsupported extension {ext!r}; "
            f"supported: {sorted(_DISPATCH_LOAD.keys())}"
        )
    return _DISPATCH_LOAD[ext](filename)
