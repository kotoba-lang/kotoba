#!/usr/bin/env python3
"""atlas_summary.py — ooyake gov-atlas shape dashboard (maturity / observability).

Read-only tally of the committed registry across all `registry/gov-units*.edn`:
counts by :gov.unit/level, by :gov.unit/branch, by :sourcing, distinct jurisdictions,
and units carrying an official-url. Makes the atlas's shape legible at a glance and
doubles as a sanity gate (exits non-zero only if the registry fails to parse).

Usage: python3 atlas_summary.py
"""
from __future__ import annotations

import glob
import os
import sys
from collections import Counter

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "cells", "reconcile")))
from cell import parse_edn  # noqa: E402

_REG = os.path.normpath(os.path.join(_HERE, "..", "registry"))


def main() -> int:
    units = {}
    for f in sorted(glob.glob(os.path.join(_REG, "gov-units*.edn"))):
        for u in parse_edn(open(f, encoding="utf-8").read()).get(":units", []):
            if u.get(":gov.unit/id"):
                units[u[":gov.unit/id"]] = u
    by_level = Counter(u.get(":gov.unit/level", "—") for u in units.values())
    by_branch = Counter(u.get(":gov.unit/branch", "—") for u in units.values())
    by_src = Counter(u.get(":gov.unit/sourcing", "—") for u in units.values())
    juris = {u.get(":gov.unit/jurisdiction", "—") for u in units.values()}
    with_url = sum(1 for u in units.values() if u.get(":gov.unit/official-url"))
    with_qid = sum(1 for u in units.values() if u.get(":gov.unit/wikidata"))

    print(f"ooyake gov-atlas summary — {len(units)} units, {len(juris)} distinct jurisdictions")
    print(f"  with Wikidata QID: {with_qid}   with official-url: {with_url}")
    print("  by sourcing:   " + "  ".join(f"{k} {v}" for k, v in by_src.most_common()))
    print("  by level:")
    for k, v in by_level.most_common():
        print(f"      {k:16} {v}")
    print("  by branch:")
    for k, v in by_branch.most_common():
        print(f"      {str(k):18} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
