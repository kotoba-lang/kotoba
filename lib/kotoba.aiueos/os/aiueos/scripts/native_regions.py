"""The Browser surface/context placement the native gates rely on, in one place (JUN-544, ADR-0276 part A step (a)).

Every gate that reads the guest's surface or context window uses these names instead of its own literals. The
authoritative definition is the compiler's: kotoba-lang/amu seed/97-aiueos-desktop-regions.kotoba (WG-WINDOW-BYTES,
WG-SURFACE, WG-CONTEXT, WG-RW-SLACK, WG-RW-MEMSZ). verify_amu() reads that file and refuses when this table differs,
and the desktop build calls it for the Amu checkout it builds with, so a gate cannot keep a layout the compiler no
longer has. Offsets are from the RW segment base (the browser context base of the kernel ELF's RW program header).
"""
import re
from pathlib import Path

WINDOW_BYTES = 8192
SURFACE_OFFSET = 0x238000
CONTEXT_OFFSET = SURFACE_OFFSET + WINDOW_BYTES
RW_SLACK = 0x4000
RW_MEMSZ = CONTEXT_OFFSET + WINDOW_BYTES + RW_SLACK

TABLE = {"WG-WINDOW-BYTES": WINDOW_BYTES, "WG-SURFACE": SURFACE_OFFSET, "WG-CONTEXT": CONTEXT_OFFSET,
         "WG-RW-SLACK": RW_SLACK, "WG-RW-MEMSZ": RW_MEMSZ}


class RegionMismatch(Exception):
    pass


def _eval(expr, defs):
    """A number, a name already defined, or (+ a b), as seed/97 writes them."""
    expr = expr.strip()
    if re.fullmatch(r"0x[0-9a-fA-F]+|[0-9]+", expr):
        return int(expr, 0)
    if expr in defs:
        return defs[expr]
    m = re.fullmatch(r"\(\+ (.+)\)", expr)
    if m:
        body, parts, depth, cur = m.group(1), [], 0, ""
        for ch in body:
            if ch == "(": depth += 1
            if ch == ")": depth -= 1
            if ch == " " and depth == 0:
                parts.append(cur); cur = ""
            else:
                cur += ch
        parts.append(cur)
        return sum(_eval(p, defs) for p in parts if p)
    raise RegionMismatch(f"cannot evaluate {expr!r}")


def amu_table(seed97_text):
    defs = {}
    for name, expr in re.findall(r"^\(def (WG-[A-Z-]+) (.+)\)\s*$", seed97_text, re.M):
        defs[name] = _eval(expr, defs)
    return {k: defs[k] for k in TABLE if k in defs}


def verify_text(seed97_text):
    got = amu_table(seed97_text)
    if got != TABLE:
        raise RegionMismatch(f"the gates' region table {TABLE} differs from the compiler's {got}")
    return got


def verify_amu(amu_source):
    return verify_text((Path(amu_source) / "seed/97-aiueos-desktop-regions.kotoba").read_text())
