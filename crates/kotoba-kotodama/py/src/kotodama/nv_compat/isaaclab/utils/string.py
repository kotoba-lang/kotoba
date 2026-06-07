"""isaaclab.utils.string — regex name matching + callable round-trip helpers.

Mirror of `isaaclab.utils.string` (Isaac Lab 1.x). Foundational helpers for
two Isaac Lab patterns:

1. **Regex joint-name matching** — actuators, sensors, and observation
   terms identify joints by NAME (not index). Cfgs accept lists of
   `[".*_hip", "wheel_lf"]` patterns; `resolve_matching_names` walks the
   full articulation joint list and returns the matched (indices, names)
   tuple. Used in iter 45 actuator setup, iter 34 RayCaster mount, etc.

2. **String ↔ callable round-trip** — Isaac Lab cfg files store reward
   / event functions as `"my.module:my_func"` strings (for YAML round-
   trip). `string_to_callable` resolves on load; `callable_to_string`
   serializes on save. Lambda expressions are detected + preserved.

Public surface:
  - resolve_matching_names(patterns, names, preserve_order=False) →
        (indices, matched_names)
  - resolve_matching_names_values(patterns_values, names) →
        (indices, matched_names, matched_values)
  - is_lambda_expression(s) → bool
  - string_to_callable(s) → callable
  - callable_to_string(fn) → str
  - to_camel_case(s, lower=False) → str
  - to_snake_case(s) → str

Pure stdlib (re + importlib).
"""

from __future__ import annotations

import importlib
import re
from typing import Any, Callable, List, Tuple


# ────────────────────────────────────────────────────────────────────────────
# Regex name matching
# ────────────────────────────────────────────────────────────────────────────


def resolve_matching_names(
    patterns: List[str],
    names: List[str],
    preserve_order: bool = False,
) -> Tuple[List[int], List[str]]:
    """Resolve a list of regex patterns into matching indices + names.

    Each pattern is full-match'd against every name. Returns the
    (indices, matched_names) pair where:
      - indices[i] = position of matched_names[i] in `names`
      - When `preserve_order=False` (default): output is sorted by name
        index ascending (Isaac Lab default).
      - When `preserve_order=True`: output follows `patterns` order — for
        each pattern, append every newly-matched name (no duplicates).
        Useful when you want pattern[0]'s matches before pattern[1]'s.

    Duplicate matches (a name hit by multiple patterns) are de-duplicated.
    No-match patterns are silently ignored; an entirely-empty `patterns`
    or `names` returns empty lists.
    """
    if not isinstance(patterns, list) or not isinstance(names, list):
        raise TypeError("patterns and names must be lists of strings")

    matched_indices: List[int] = []
    matched_names: List[str] = []
    seen_indices = set()

    if preserve_order:
        # Walk patterns in order; for each, scan names left-to-right.
        for pat in patterns:
            try:
                regex = re.compile(pat)
            except re.error as e:
                raise ValueError(f"invalid regex pattern {pat!r}: {e}") from None
            for i, name in enumerate(names):
                if regex.fullmatch(name) and i not in seen_indices:
                    matched_indices.append(i)
                    matched_names.append(name)
                    seen_indices.add(i)
    else:
        # Sorted-by-name-index output: walk names; for each, test all patterns.
        try:
            regexes = [re.compile(p) for p in patterns]
        except re.error as e:
            raise ValueError(f"invalid regex pattern in {patterns}: {e}") from None
        for i, name in enumerate(names):
            for regex in regexes:
                if regex.fullmatch(name):
                    matched_indices.append(i)
                    matched_names.append(name)
                    break  # one match is enough

    return matched_indices, matched_names


def resolve_matching_names_values(
    patterns_values: List[Tuple[str, Any]],
    names: List[str],
    preserve_order: bool = False,
) -> Tuple[List[int], List[str], List[Any]]:
    """Like `resolve_matching_names`, but each pattern pairs with a value.

    `patterns_values` is a list of `(pattern, value)` tuples. For each
    matching name, returns the matching value. Used in Isaac Lab actuator
    cfgs to pair joint regex patterns with per-joint stiffness / damping
    values:

        stiffness = [
            ("hip_.*", 100.0),
            ("knee_.*", 200.0),
            ("ankle_.*", 50.0),
        ]
        ids, names, ks = resolve_matching_names_values(stiffness, joint_names)
        # ids = matched joint indices; ks = parallel value list

    Duplicate matches: the FIRST pattern wins (later patterns are ignored
    for already-matched names).
    """
    if not isinstance(patterns_values, list) or not isinstance(names, list):
        raise TypeError("patterns_values and names must be lists")
    for pv in patterns_values:
        if not (isinstance(pv, (tuple, list)) and len(pv) == 2):
            raise TypeError(
                f"patterns_values entries must be (pattern, value) tuples; got {pv}"
            )

    matched_indices: List[int] = []
    matched_names: List[str] = []
    matched_values: List[Any] = []
    seen_indices = set()

    try:
        regexes = [(re.compile(p), v) for p, v in patterns_values]
    except re.error as e:
        raise ValueError(f"invalid regex in patterns_values: {e}") from None

    if preserve_order:
        for regex, value in regexes:
            for i, name in enumerate(names):
                if regex.fullmatch(name) and i not in seen_indices:
                    matched_indices.append(i)
                    matched_names.append(name)
                    matched_values.append(value)
                    seen_indices.add(i)
    else:
        for i, name in enumerate(names):
            for regex, value in regexes:
                if regex.fullmatch(name):
                    matched_indices.append(i)
                    matched_names.append(name)
                    matched_values.append(value)
                    break  # first match wins

    return matched_indices, matched_names, matched_values


# ────────────────────────────────────────────────────────────────────────────
# Lambda detection + string ↔ callable
# ────────────────────────────────────────────────────────────────────────────


_LAMBDA_RE = re.compile(r"^\s*lambda\b")


def is_lambda_expression(s: str) -> bool:
    """True if `s` is a string that starts with `lambda` (possibly preceded
    by whitespace). Used to dispatch `string_to_callable` between import-
    path resolution and `eval`."""
    if not isinstance(s, str):
        return False
    return bool(_LAMBDA_RE.match(s))


def string_to_callable(name: str) -> Callable[..., Any]:
    """Resolve a string to a callable. Two forms:

    1. `"module.path:attr"` — Hydra/Isaac Lab convention. Imports the
       module and walks attributes. Same as `task_registry`'s `_resolve`.
    2. `"module.path.attr"` — last dotted part is treated as the attr.
    3. `"lambda x: x + 1"` — eval'd as a Python expression.

    Raises ValueError on unparseable input; ImportError / AttributeError
    on missing target.
    """
    if not isinstance(name, str):
        raise TypeError(f"string_to_callable expects str; got {type(name).__name__}")
    name = name.strip()
    if not name:
        raise ValueError("empty string is not a callable")

    if is_lambda_expression(name):
        # Lambda — eval in a restricted globals dict to avoid name leakage.
        # Note: this is intentional eval of the cfg-supplied lambda; the
        # cfg is treated as trusted code (matches Isaac Lab semantics).
        try:
            return eval(name, {"__builtins__": __builtins__})
        except SyntaxError as e:
            raise ValueError(f"invalid lambda expression {name!r}: {e}") from None

    if ":" in name:
        # Hydra/Isaac Lab "module:attr.path" convention.
        module_path, attr_path = name.split(":", 1)
    else:
        # Plain dotted "module.attr" — split off the last component as attr.
        if "." not in name:
            raise ValueError(
                f"{name!r} is not a valid callable reference "
                f"(expected 'module:attr', 'module.path.attr', or 'lambda ...')"
            )
        module_path, _, attr_path = name.rpartition(".")

    module = importlib.import_module(module_path)
    obj: Any = module
    for part in attr_path.split("."):
        obj = getattr(obj, part)
    if not callable(obj):
        raise TypeError(f"{name!r} resolves to a non-callable {type(obj).__name__}")
    return obj


def callable_to_string(fn: Callable[..., Any]) -> str:
    """Serialize a callable back to a `"module:attr"` string.

    Lambdas and locally-defined callables (no `__module__` / `__qualname__`)
    raise ValueError — Isaac Lab cfg files can't round-trip those.
    """
    if not callable(fn):
        raise TypeError(f"callable_to_string expects callable; got {type(fn).__name__}")
    module = getattr(fn, "__module__", None)
    qualname = getattr(fn, "__qualname__", None) or getattr(fn, "__name__", None)
    if not module or not qualname:
        raise ValueError(f"cannot serialize {fn!r} — missing __module__ / __qualname__")
    if "<lambda>" in qualname or "<locals>" in qualname:
        raise ValueError(
            f"cannot serialize {fn!r} — lambdas / local functions are not "
            f"importable; supply a module-level def instead"
        )
    return f"{module}:{qualname}"


# ────────────────────────────────────────────────────────────────────────────
# Case conversion
# ────────────────────────────────────────────────────────────────────────────


_CAMEL_RE_1 = re.compile(r"(.)([A-Z][a-z]+)")
_CAMEL_RE_2 = re.compile(r"([a-z0-9])([A-Z])")


def to_snake_case(s: str) -> str:
    """Convert CamelCase / camelCase / kebab-case → snake_case.

    Examples:
      "MyClass"      → "my_class"
      "myClass"      → "my_class"
      "MyXMLParser"  → "my_xml_parser"
      "kebab-case"   → "kebab_case"
      "already_snake" → "already_snake"
    """
    s = s.replace("-", "_")
    s = _CAMEL_RE_1.sub(r"\1_\2", s)
    s = _CAMEL_RE_2.sub(r"\1_\2", s)
    return s.lower()


def to_camel_case(s: str, lower: bool = False) -> str:
    """Convert snake_case / kebab-case → CamelCase.

    `lower=True` produces lowerCamelCase; default is UpperCamelCase.

    Strings without separators (`_` or `-`) are passed through unchanged
    (matches Isaac Lab semantics — `to_camel_case("AlreadyCamel")` returns
    `"AlreadyCamel"` so the function is idempotent on already-camel input).

    Examples:
      "my_class"      → "MyClass"
      "my_class" (lower=True) → "myClass"
      "kebab-case"    → "KebabCase"
      "AlreadyCamel"  → "AlreadyCamel"  (no separators → unchanged)
    """
    if "_" not in s and "-" not in s:
        return s
    parts = re.split(r"[_\-]", s)
    if not parts:
        return s
    # Capitalize the first letter of each part, preserve the rest as-is
    # (don't use str.title() because it lowercases interior caps).
    def cap_first(p: str) -> str:
        return p[:1].upper() + p[1:] if p else p
    if lower:
        first = parts[0].lower() if parts[0] else ""
        return first + "".join(cap_first(p) for p in parts[1:])
    return "".join(cap_first(p) for p in parts)
