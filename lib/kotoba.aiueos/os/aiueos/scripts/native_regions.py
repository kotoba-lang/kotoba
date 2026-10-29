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


def _seed_value(text, pattern, what):
    m = re.search(pattern, text, re.M)
    if not m:
        raise RegionMismatch(f"the compiler no longer defines {what}")
    return m


def verify_layout_text(seed95_text, seed85_text, table):
    """native/layout-table.json must carry the compiler's page-table roots and text caps (one row per RW rung)."""
    pml4 = int(_seed_value(seed95_text, r"^\(def UV-PML4 (0x[0-9a-fA-F]+)\)", "UV-PML4").group(1), 16)
    v5 = int(_seed_value(seed95_text, r"^\(def UV-V5-PML4 (0x[0-9a-fA-F]+)\)", "UV-V5-PML4").group(1), 16)
    cap = _seed_value(seed85_text, r"\(defn- kp-text-cap \[\] :i64 \(if \(or \(kp-v2\?\) \(kp-v3\?\)\) (\d+) (\d+)\)\)", "kp-text-cap")
    want = {"0x200000": (pml4, int(cap.group(2))), "0x400000": (v5, int(cap.group(1)))}
    rungs = table.get("rungs", {})
    if set(rungs) != set(want):
        raise RegionMismatch(f"the layout table has rungs {sorted(rungs)}, the compiler's are {sorted(want)}")
    for rung, (root, text_cap) in want.items():
        row = rungs[rung]
        if int(row["pageTableRootOffset"], 16) != root or row["compilerTextCapBytes"] != text_cap:
            raise RegionMismatch(f"layout table rung {rung}: {row['pageTableRootOffset']}/{row['compilerTextCapBytes']} "
                                 f"differs from the compiler's {hex(root)}/{text_cap}")
    return want


def verify_layout(amu_source, table_path):
    import json
    amu = Path(amu_source)
    return verify_layout_text((amu / "seed/95-aiueos-user-context.kotoba").read_text(),
                              (amu / "seed/85-aiueos-project.kotoba").read_text(),
                              json.loads(Path(table_path).read_text()))
