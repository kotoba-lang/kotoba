"""isaaclab.utils.dict — cfg serialization + dict-utility helpers.

Mirror of `isaaclab.utils.dict` (Isaac Lab 1.x). Used across Isaac Lab for:

  - checkpoint save  : `class_to_dict(cfg)` → JSON / YAML serializable
  - checkpoint restore : `update_class_from_dict(cfg, ckpt_dict)`
  - Hydra-style overrides : `deep_update(cfg_dict, override_dict)`
  - debug logging : `print_dict(cfg_to_dict(env.cfg))` + `dict_to_md_table`
  - slice round-trip : the "joint_names": "[0:5]" Isaac Lab cfg pattern
    needs `replace_strings_with_slices` (load) + `replace_slices_with_strings`
    (save) to survive YAML round-trips

Public surface:
  - class_to_dict(obj, exclude_keys=())   — recursive class → dict
  - update_class_from_dict(obj, d)        — recursive dict → class
  - deep_update(target, source)           — recursive dict merge (in-place)
  - print_dict(d, header="", indent=2)    — pretty multi-line print
  - dict_to_md_table(d, header=("Key","Value"))
                                          — flat dict → 2-col MD table
  - iterable_to_string(it, sep=", ")      — short list/tuple repr
  - replace_strings_with_slices(d)        — "[0:5]" str → slice(0,5)
  - replace_slices_with_strings(d)        — inverse

Pure stdlib. Handles dataclasses, plain classes with attributes, dicts,
lists, tuples, sets transparently.
"""

from __future__ import annotations

import re
from dataclasses import fields, is_dataclass
from typing import Any, Iterable, Tuple


# ────────────────────────────────────────────────────────────────────────────
# class_to_dict / update_class_from_dict
# ────────────────────────────────────────────────────────────────────────────


def class_to_dict(obj: Any, exclude_keys: Iterable[str] = ()) -> Any:
    """Recursively convert a class instance / dataclass / nested container
    into a plain dict / list / scalar.

    Handles:
      - dataclass instances → {field.name: class_to_dict(value)}
      - plain class instances (with __dict__) → {attr: class_to_dict(value)}
      - dict / list / tuple / set → recurse element-wise
      - scalars (int, float, str, bool, None) → returned as-is
      - everything else (functions, modules, types) → string repr

    `exclude_keys` is applied at every level (top-level + nested
    class/dict). Useful for stripping volatile / non-serializable fields.
    """
    excluded = set(exclude_keys)

    def _walk(o: Any) -> Any:
        if o is None or isinstance(o, (bool, int, float, str)):
            return o
        if isinstance(o, dict):
            return {k: _walk(v) for k, v in o.items() if k not in excluded}
        if isinstance(o, (list, tuple)):
            kind = type(o)
            return kind(_walk(v) for v in o)
        if isinstance(o, set):
            return {_walk(v) for v in o}
        # Dataclass instance → use fields() to get declared attrs.
        if is_dataclass(o) and not isinstance(o, type):
            out = {}
            for f in fields(o):
                if f.name in excluded:
                    continue
                out[f.name] = _walk(getattr(o, f.name))
            return out
        # Plain class instance with __dict__.
        if hasattr(o, "__dict__"):
            out = {}
            for k, v in vars(o).items():
                if k.startswith("_") or k in excluded:
                    continue
                if callable(v) and not isinstance(v, type):
                    continue
                out[k] = _walk(v)
            return out
        # Fallback — string repr.
        return repr(o)

    return _walk(obj)


def update_class_from_dict(obj: Any, d: dict, strict: bool = False) -> None:
    """Recursively update an object's attributes from a dict.

    For each (key, value) in `d`:
      - If `obj` has attribute `key`:
          - If both attribute and value are dict-like / class-like, recurse
          - Otherwise assign directly
      - If `obj` lacks attribute `key`:
          - `strict=True`  → AttributeError
          - `strict=False` (default) → silently skip

    Mirrors Isaac Lab's checkpoint-restore convention (permissive: extra
    keys in saved dict are tolerated when restoring into an older cfg
    class). Use `strict=True` for cfg-from-CLI flows where typos should
    fail loudly.
    """
    if not isinstance(d, dict):
        raise TypeError(f"update_class_from_dict source must be dict; got {type(d).__name__}")
    for key, value in d.items():
        if not hasattr(obj, key):
            if strict:
                raise AttributeError(
                    f"{type(obj).__name__} has no attribute '{key}'"
                )
            continue
        current = getattr(obj, key)
        # Nested dict + nested class → recurse.
        if (
            isinstance(value, dict)
            and current is not None
            and not isinstance(current, dict)
            and (hasattr(current, "__dict__") or is_dataclass(current))
        ):
            update_class_from_dict(current, value, strict=strict)
            continue
        # Nested dict + current dict → recursive deep_update.
        if isinstance(value, dict) and isinstance(current, dict):
            deep_update(current, value)
            continue
        # Direct assignment.
        setattr(obj, key, value)


# ────────────────────────────────────────────────────────────────────────────
# deep_update
# ────────────────────────────────────────────────────────────────────────────


def deep_update(target: dict, source: dict) -> dict:
    """Recursively merge `source` into `target` in-place. Mirrors the
    Hydra / OmegaConf deep-merge convention: nested dicts merge,
    scalars + lists at a key overwrite.

    Returns the target dict (for chaining).
    """
    if not isinstance(target, dict) or not isinstance(source, dict):
        raise TypeError("deep_update requires both target and source to be dict")
    for key, value in source.items():
        if (
            key in target
            and isinstance(target[key], dict)
            and isinstance(value, dict)
        ):
            deep_update(target[key], value)
        else:
            target[key] = value
    return target


# ────────────────────────────────────────────────────────────────────────────
# print_dict + dict_to_md_table + iterable_to_string
# ────────────────────────────────────────────────────────────────────────────


def print_dict(d: dict, header: str = "", indent: int = 2) -> None:
    """Pretty-print a nested dict to stdout. Mirrors Isaac Lab's
    `utils.dict.print_dict` formatting (key=value on lines, nested dicts
    indented). Lists / tuples render via iterable_to_string.
    """
    if header:
        print(header)
    _print_dict_inner(d, indent_level=0, indent_step=indent)


def _print_dict_inner(d: dict, indent_level: int, indent_step: int) -> None:
    pad = " " * (indent_level * indent_step)
    if not isinstance(d, dict):
        print(f"{pad}{d}")
        return
    for k, v in d.items():
        if isinstance(v, dict):
            print(f"{pad}{k}:")
            _print_dict_inner(v, indent_level + 1, indent_step)
        elif isinstance(v, (list, tuple)):
            print(f"{pad}{k}: {iterable_to_string(v)}")
        else:
            print(f"{pad}{k}: {v}")


def dict_to_md_table(
    d: dict,
    header: Tuple[str, str] = ("Key", "Value"),
) -> str:
    """Render a flat (or one-level-nested) dict as a 2-column Markdown table.

    Nested dicts are joined to a single string via `iterable_to_string`
    so the table stays 2-col. For arbitrarily nested rendering use
    `print_dict` instead.
    """
    if not isinstance(d, dict):
        raise TypeError("dict_to_md_table requires a dict")
    rows = [f"| {header[0]} | {header[1]} |", "|---|---|"]
    for k, v in d.items():
        if isinstance(v, dict):
            v_str = iterable_to_string(
                [f"{kk}={vv}" for kk, vv in v.items()]
            )
        elif isinstance(v, (list, tuple)):
            v_str = iterable_to_string(v)
        else:
            v_str = str(v)
        rows.append(f"| {k} | {v_str} |")
    return "\n".join(rows)


def iterable_to_string(it: Iterable[Any], sep: str = ", ") -> str:
    """Compact string repr of a list/tuple/set. Long sequences are
    truncated to first 4 + '...' + last 1 for readability."""
    items = list(it)
    if len(items) <= 6:
        return "[" + sep.join(str(x) for x in items) + "]"
    head = sep.join(str(x) for x in items[:4])
    return f"[{head}{sep}... {sep}{items[-1]}]"


# ────────────────────────────────────────────────────────────────────────────
# Slice round-trip (Isaac Lab cfg pattern)
# ────────────────────────────────────────────────────────────────────────────


_SLICE_RE = re.compile(r"^\[(-?\d+)?:(-?\d+)?(?::(-?\d+))?\]$")


def _parse_slice_string(s: str):
    """Convert "[0:5]" / "[:5]" / "[0:5:2]" to a slice object. Returns
    the original string if it doesn't look like a slice spec."""
    if not isinstance(s, str):
        return s
    m = _SLICE_RE.match(s.strip())
    if not m:
        return s
    parts = m.groups()
    start = int(parts[0]) if parts[0] is not None else None
    stop = int(parts[1]) if parts[1] is not None else None
    step = int(parts[2]) if parts[2] is not None else None
    return slice(start, stop, step)


def _slice_to_string(sl: slice) -> str:
    """Convert slice → "[start:stop:step]" string."""
    start = "" if sl.start is None else str(sl.start)
    stop = "" if sl.stop is None else str(sl.stop)
    if sl.step is not None:
        return f"[{start}:{stop}:{sl.step}]"
    return f"[{start}:{stop}]"


def replace_strings_with_slices(d: Any) -> Any:
    """Recursively replace `"[a:b]"` string values with `slice(a, b)` objects.

    Isaac Lab cfg files keep slice specs as strings for YAML round-trip
    compatibility; this function converts them back to real slice objects
    at load time. Handles nested dicts / lists / tuples / class instances.
    """
    if isinstance(d, dict):
        return {k: replace_strings_with_slices(v) for k, v in d.items()}
    if isinstance(d, list):
        return [replace_strings_with_slices(v) for v in d]
    if isinstance(d, tuple):
        return tuple(replace_strings_with_slices(v) for v in d)
    if isinstance(d, str):
        return _parse_slice_string(d)
    if hasattr(d, "__dict__") and not isinstance(d, type):
        for k, v in list(vars(d).items()):
            if k.startswith("_"):
                continue
            setattr(d, k, replace_strings_with_slices(v))
        return d
    return d


def replace_slices_with_strings(d: Any) -> Any:
    """Inverse of replace_strings_with_slices — converts slice → "[a:b]"
    string for serialization.
    """
    if isinstance(d, dict):
        return {k: replace_slices_with_strings(v) for k, v in d.items()}
    if isinstance(d, list):
        return [replace_slices_with_strings(v) for v in d]
    if isinstance(d, tuple):
        return tuple(replace_slices_with_strings(v) for v in d)
    if isinstance(d, slice):
        return _slice_to_string(d)
    if hasattr(d, "__dict__") and not isinstance(d, type):
        for k, v in list(vars(d).items()):
            if k.startswith("_"):
                continue
            setattr(d, k, replace_slices_with_strings(v))
        return d
    return d
