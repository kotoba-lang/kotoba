"""IExt base class + minimal extension.toml parser.

`IExt` mirrors `omni.ext.IExt` (the Omniverse Kit extension base). Subclasses
override `on_startup(ext_id)` and `on_shutdown()`. The Application invokes
these in dependency order.

`ExtensionToml` is the parsed form of `extension.toml`:

    [package]
    title = "My Extension"
    version = "1.0.0"
    description = "..."

    [dependencies]
    "omni.kit.uiapp" = {}
    "omni.usd" = {}

    [[python.module]]
    name = "my_ext"

`parse_extension_toml(text)` returns an ExtensionToml. The parser handles
the subset of TOML actually used in Kit extension manifests; nested tables
and arrays-of-tables for [[python.module]] are supported. Pure stdlib,
Pyodide-compatible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class IExt:
    """Base class for Kit extensions. Override on_startup / on_shutdown."""

    def on_startup(self, ext_id: str) -> None:
        """Called when the Application loads this extension."""
        pass

    def on_shutdown(self) -> None:
        """Called when the Application unloads this extension."""
        pass


@dataclass
class ExtensionToml:
    """Parsed extension.toml metadata (subset)."""
    title: str = ""
    version: str = "0.1.0"
    description: str = ""
    category: str = ""
    keywords: List[str] = field(default_factory=list)
    authors: List[str] = field(default_factory=list)
    repository: str = ""
    dependencies: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    python_modules: List[Dict[str, Any]] = field(default_factory=list)
    # Raw section content keyed by full dotted name (e.g. "package", "python.module").
    raw_tables: Dict[str, Any] = field(default_factory=dict)


def _strip_comment(line: str) -> str:
    """Remove # comments while respecting strings."""
    in_string = False
    out_chars = []
    i = 0
    while i < len(line):
        c = line[i]
        if c == '"' and (i == 0 or line[i - 1] != "\\"):
            in_string = not in_string
        if c == "#" and not in_string:
            break
        out_chars.append(c)
        i += 1
    return "".join(out_chars)


def _parse_value(raw: str) -> Any:
    raw = raw.strip()
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        # List of values; split on commas at top level.
        out: list = []
        depth = 0
        cur: list = []
        for ch in inner:
            if ch in "[{":
                depth += 1
            elif ch in "]}":
                depth -= 1
            if ch == "," and depth == 0:
                out.append(_parse_value("".join(cur)))
                cur = []
            else:
                cur.append(ch)
        if cur:
            out.append(_parse_value("".join(cur)))
        return out
    if raw.startswith("{") and raw.endswith("}"):
        inner = raw[1:-1].strip()
        if not inner:
            return {}
        out_d: dict = {}
        for part in inner.split(","):
            kv = part.split("=", 1)
            if len(kv) == 2:
                out_d[kv[0].strip().strip('"')] = _parse_value(kv[1].strip())
        return out_d
    if raw.lower() in ("true", "false"):
        return raw.lower() == "true"
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def parse_extension_toml(text: str) -> ExtensionToml:
    """Minimal TOML parser for Kit extension manifests."""
    result = ExtensionToml()
    current_table: Optional[str] = None
    is_array_of_tables = False
    table_stack: List[tuple] = []  # (key, dict-target)

    def get_table(name: str, is_array: bool = False):
        # Build / return the dict matching the dotted-key name.
        parts = name.split(".")
        if is_array:
            # arrays of tables: place a list under the dotted path
            cur = result.raw_tables
            for i, p in enumerate(parts[:-1]):
                if p not in cur:
                    cur[p] = {}
                cur = cur[p]
            last = parts[-1]
            if last not in cur:
                cur[last] = []
            new_entry: Dict[str, Any] = {}
            cur[last].append(new_entry)
            return new_entry
        else:
            cur = result.raw_tables
            for p in parts:
                if p not in cur:
                    cur[p] = {}
                cur = cur[p]
            return cur

    active_table: Dict[str, Any] = result.raw_tables
    for raw_line in text.splitlines():
        line = _strip_comment(raw_line).strip()
        if not line:
            continue
        if line.startswith("[[") and line.endswith("]]"):
            name = line[2:-2].strip()
            active_table = get_table(name, is_array=True)
            current_table = name
            is_array_of_tables = True
            continue
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1].strip()
            active_table = get_table(name, is_array=False)
            current_table = name
            is_array_of_tables = False
            continue
        # key = value
        m = re.match(r'^"?([^"=]+)"?\s*=\s*(.*)$', line)
        if not m:
            continue
        key = m.group(1).strip().strip('"')
        value = _parse_value(m.group(2))
        active_table[key] = value

    # Hydrate convenience fields from raw_tables.
    pkg = result.raw_tables.get("package", {})
    if isinstance(pkg, dict):
        result.title = pkg.get("title", "")
        result.version = pkg.get("version", "0.1.0")
        result.description = pkg.get("description", "")
        result.category = pkg.get("category", "")
        result.keywords = pkg.get("keywords", []) or []
        result.authors = pkg.get("authors", []) or []
        result.repository = pkg.get("repository", "")
    deps = result.raw_tables.get("dependencies", {})
    if isinstance(deps, dict):
        result.dependencies = deps
    py = result.raw_tables.get("python", {})
    if isinstance(py, dict):
        mods = py.get("module", [])
        if isinstance(mods, list):
            result.python_modules = mods
    return result
