#!/usr/bin/env python3
"""Controls for native_regions.verify_*: the real seed/97 of an Amu checkout agrees, and altered definitions are refused."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_regions as r

amu = Path(sys.argv[1])
text = (amu / "seed/97-aiueos-desktop-regions.kotoba").read_text()
assert r.verify_text(text) == r.TABLE, "the compiler's table must equal the gates' table"
for what, old, new in (("window size", "(def WG-WINDOW-BYTES 8192)", "(def WG-WINDOW-BYTES 16384)"),
                       ("surface offset", "(def WG-SURFACE 0x238000)", "(def WG-SURFACE 0x238001)"),
                       ("slack", "(def WG-RW-SLACK 0x4000)", "(def WG-RW-SLACK 0x2000)")):
    assert old in text, (what, "the control cannot be built: the definition is absent")
    try:
        r.verify_text(text.replace(old, new, 1))
    except r.RegionMismatch:
        continue
    raise AssertionError(f"an altered {what} was accepted")
try:
    r.verify_text(text.replace("(def WG-RW-MEMSZ", "(def WG-OTHER", 1))
except r.RegionMismatch:
    pass
else:
    raise AssertionError("a table without WG-RW-MEMSZ was accepted")
# the layout table (page-table roots and text caps per RW rung) against seed/95 and seed/85
import json
table = json.loads((Path(__file__).resolve().parent.parent / "native/layout-table.json").read_text())
t95 = (amu / "seed/95-aiueos-user-context.kotoba").read_text()
t85 = (amu / "seed/85-aiueos-project.kotoba").read_text()
r.verify_layout_text(t95, t85, table)
for what, a, b, c in (("v1 page-table root", t95.replace("(def UV-PML4 0x30000)", "(def UV-PML4 0x31000)", 1), t85, table),
                      ("v3 page-table root", t95.replace("(def UV-V5-PML4 0x130000)", "(def UV-V5-PML4 0x131000)", 1), t85, table),
                      ("text cap", t95, t85.replace("2097152 1048576)", "2097152 524288)", 1), table),
                      ("missing rung", t95, t85, {"rungs": {"0x200000": table["rungs"]["0x200000"]}}),
                      ("stale row", t95, t85, {"rungs": {**table["rungs"], "0x400000": {**table["rungs"]["0x400000"], "pageTableRootOffset": "0x30000"}}})):
    try:
        r.verify_layout_text(a, b, c)
    except r.RegionMismatch:
        continue
    raise AssertionError(f"an altered {what} was accepted")
print("PASS_NATIVE_REGIONS_TABLE", r.TABLE)
