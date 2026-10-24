#!/usr/bin/env python3
"""quality_audit.py — flag likely sub-national / mis-typed NATIONAL bodies (maturity).

The bulk Wikidata class-pulls occasionally tagged a sub-national or historical body to
a country (e.g. a state competition office, a provincial archive). This read-only audit
scans national-level units (gov.<iso3>.<suffix>, excluding :country and :subdivision)
and flags high-precision sub-national / former signals in the English name so a
maintainer can review + correct them. Reports only — never edits.

Exit 0 always (informational); prints a per-signal list. Wire into run_tests.sh to keep
the flag count visible over time.

Usage: python3 quality_audit.py [--max N]
"""
from __future__ import annotations

import glob
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "cells", "reconcile")))
from cell import parse_edn  # noqa: E402

_REG = os.path.normpath(os.path.join(_HERE, "..", "registry"))

# high-precision sub-national / historical signals (avoid "state"/"national" which are
# legitimate at national level — e.g. "Secretary of State", "National Assembly")
SIGNALS = [
    ("former/abolished", re.compile(r"\b(former|abolished|defunct)\b", re.I)),
    # high-precision sub-national words ("regional"/"historical" alone are too noisy —
    # legit at national level: "Regional Integration", "National Historical Archive")
    ("provincial/county", re.compile(r"\b(provincial|province of|cantonal|prefectural|county|district attorney)\b", re.I)),
    ("named sub-state region", re.compile(
        r"\b(Qu[eé]bec|Scotland|Wales|Northern Ireland|Catalonia|Bavaria|Hessian|Flanders|Wallonia|"
        r"New South Wales|Queensland|Tasmania|Zanzibar|Hong Kong|Macau|Puerto Rico|Greenland|"
        r"Faisalabad|of California|of Texas)\b"),),
]


def main() -> int:
    mx = 8
    if "--max" in sys.argv:
        mx = int(sys.argv[sys.argv.index("--max") + 1])
    units = {}
    for f in sorted(glob.glob(os.path.join(_REG, "gov-units*.edn"))):
        for u in parse_edn(open(f, encoding="utf-8").read()).get(":units", []):
            if u.get(":gov.unit/id"):
                units[u[":gov.unit/id"]] = u
    nat = re.compile(r"^gov\.[a-z]{3}\.[a-z0-9-]+$")
    flagged = {sig: [] for sig, _ in SIGNALS}
    for uid, u in sorted(units.items()):
        if not nat.match(uid):
            continue
        if u.get(":gov.unit/level") in (":country", ":subdivision"):
            continue
        nm = u.get(":gov.unit/name-en") or ""
        for sig, rx in SIGNALS:
            if rx.search(nm):
                flagged[sig].append((uid, nm))
                break
    total = sum(len(v) for v in flagged.values())
    natcount = sum(1 for uid, u in units.items()
                   if nat.match(uid) and u.get(":gov.unit/level") not in (":country", ":subdivision"))
    print(f"ooyake quality audit — {natcount:,} national-level bodies scanned, "
          f"{total} flagged for review ({round(100*total/max(1,natcount),2)}%)")
    for sig, _ in SIGNALS:
        rows = flagged[sig]
        if not rows:
            continue
        print(f"  [{sig}] {len(rows)}")
        for uid, nm in rows[:mx]:
            print(f"      {uid:34} {nm}")
        if len(rows) > mx:
            print(f"      … +{len(rows)-mx} more")
    if total == 0:
        print("  clean — no sub-national/historical signals in national-body names")
    return 0


if __name__ == "__main__":
    sys.exit(main())
