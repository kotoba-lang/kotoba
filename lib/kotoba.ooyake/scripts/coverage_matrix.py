#!/usr/bin/env python3
"""coverage_matrix.py — ooyake per-country functional-coverage dashboard (maturity).

Read-only. For each of the atlas's country units, reports which functional government
bodies are present (across ~30 canonical categories spanning the executive ministries,
the legislative/judicial branches, the central bank, and the independent
oversight/regulatory bodies), the per-country completeness, and — globally — how many
of the N countries carry each category (with a few example gaps). Makes the atlas's
*depth* legible per jurisdiction and guides where coverage is thin.

Robust to the G20/Japan units that use bespoke id suffixes (mof/treasury/boj/mext/…):
each canonical category maps to a set of accepted id suffixes.

Usage: python3 coverage_matrix.py
"""
from __future__ import annotations

import glob
import os
import re
import sys
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "cells", "reconcile")))
from cell import parse_edn  # noqa: E402

_REG = os.path.normpath(os.path.join(_HERE, "..", "registry"))

# canonical category -> accepted national-body id suffixes (standard + G20/JP bespoke)
CAT = {
    "finance": {"finance", "mof", "treasury", "minefi", "mef", "fin", "fazenda",
                "minfin", "shcp", "kemenkeu", "hmb", "economia", "moef", "bmf"},
    "foreign": {"foreign", "mofa"},
    "defense": {"defense", "mod"},
    "interior": {"interior", "mic"},
    "justice": {"justice", "moj"},
    "health": {"health", "mhlw"},
    "education": {"education", "mext"},
    "agriculture": {"agriculture", "maff"},
    "environment": {"environment", "moe"},
    "transport": {"transport", "mlit"},
    "labour": {"labour"}, "energy": {"energy"}, "culture": {"culture"},
    "trade": {"trade", "meti"}, "communications": {"communications"},
    "social": {"social"}, "housing": {"housing"}, "science": {"science"},
    "tourism": {"tourism"}, "industry": {"industry"}, "water": {"water"},
    "central-bank": {"central-bank", "boj", "fed", "boe", "banque", "bundesbank",
                     "bancaditalia", "boc", "pbc", "bcb", "cbr", "banxico", "bi",
                     "tcmb", "sarb", "bcra", "sama", "bok", "rbi", "rba"},
    "legislature": {"legislature"}, "supreme-court": {"supreme-court"},
    "audit": {"audit"}, "ombudsman": {"ombudsman"}, "electoral": {"electoral"},
    "nhri": {"nhri"}, "anticorruption": {"anticorruption"},
    "dataprotection": {"dataprotection"}, "competition": {"competition"},
    "finreg": {"finreg"}, "statistics": {"statistics"},
    "prosecutor": {"prosecutor"}, "revenue": {"revenue", "nta"},
}
SUF2CAT = {s: c for c, ss in CAT.items() for s in ss}


def main() -> int:
    units = {}
    for f in sorted(glob.glob(os.path.join(_REG, "gov-units*.edn"))):
        for u in parse_edn(open(f, encoding="utf-8").read()).get(":units", []):
            if u.get(":gov.unit/id"):
                units[u[":gov.unit/id"]] = u
    countries = sorted(j for j in {u.get(":gov.unit/jurisdiction") for u in units.values()
                                   if u.get(":gov.unit/level") == ":country"} if j and len(j) == 3)
    have = defaultdict(set)   # iso3 -> set(category)
    nat = re.compile(r"^gov\.([a-z]{3})\.([a-z0-9-]+)$")
    for uid in units:
        m = nat.match(uid)
        if not m:
            continue
        iso, suf = m.group(1), m.group(2)
        c = SUF2CAT.get(suf)
        if c:
            have[iso].add(c)
    ncat = len(CAT)
    # global per-category coverage
    cat_cov = {c: sum(1 for iso in countries if c in have[iso]) for c in CAT}
    print(f"ooyake coverage matrix — {len(countries)} country units × {ncat} functional categories")
    print(f"  (national-body presence; subnational ADM1 not counted here)\n")
    print("  GLOBAL category coverage (countries with ≥1 such body / {} countries):".format(len(countries)))
    for c, n in sorted(cat_cov.items(), key=lambda x: -x[1]):
        miss = [iso.upper() for iso in countries if c not in have[iso]][:6]
        bar = "█" * round(28 * n / max(1, len(countries)))
        print(f"      {c:15} {n:3}  {bar}  gaps: {' '.join(miss)}")
    comp = sorted(((len(have[iso]), iso) for iso in countries), reverse=True)
    avg = sum(n for n, _ in comp) / max(1, len(comp))
    print(f"\n  per-country completeness: avg {avg:.1f}/{ncat} categories")
    print("    most complete: " + ", ".join(f"{iso.upper()}({n})" for n, iso in comp[:8]))
    print("    least complete: " + ", ".join(f"{iso.upper()}({n})" for n, iso in comp[-8:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
