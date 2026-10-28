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
print("PASS_NATIVE_REGIONS_TABLE", r.TABLE)
