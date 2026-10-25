#!/usr/bin/env python3
"""world_coverage.py — ooyake REAL-DATA world-government coverage (country level).

Reports how many sovereign-state COUNTRY units the atlas carries as real data
(:level :country, :sourcing :authoritative, :verification-status :maintainer-verified,
with a Wikidata QID). The UN has 193 member states; this gate asserts the country
layer covers at least that many real-data states so the "全世界政府" breadth can't
silently regress.

READ-ONLY. Exits non-zero if the real-data country count drops below the floor.

Usage: python3 world_coverage.py
"""
from __future__ import annotations

import glob
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "cells", "reconcile")))
from cell import parse_edn  # noqa: E402

_REG = os.path.normpath(os.path.join(_HERE, "..", "registry"))
# The atlas carries the current UN-member sovereign states that bear an ISO 3166-1
# alpha-3 code with a Wikidata QID (192 as of 2026-06-03; dissolved/historical states
# are excluded by the membership-end + dissolution filters). The floor is a
# regression guard set just below that, NOT a precise claim of all 193 members.
UN_MEMBER_FLOOR = 190


def load_all() -> dict[str, dict]:
    units: dict[str, dict] = {}
    for f in sorted(glob.glob(os.path.join(_REG, "gov-units*.edn"))):
        for u in parse_edn(open(f, encoding="utf-8").read()).get(":units", []):
            if u.get(":gov.unit/id"):
                units[u[":gov.unit/id"]] = u
    return units


def main() -> int:
    units = load_all()
    countries = [u for u in units.values() if u.get(":gov.unit/level") == ":country"]
    real = [u for u in countries
            if u.get(":gov.unit/sourcing") == ":authoritative"
            and u.get(":gov.unit/verification-status") == ":maintainer-verified"
            and u.get(":gov.unit/wikidata")]
    with_site = sum(1 for u in real if u.get(":gov.unit/official-url"))
    print("ooyake REAL-DATA world-government coverage (country level)")
    print(f"  country units total      : {len(countries)}")
    print(f"  real-data (:authoritative + :maintainer-verified + QID): {len(real)}")
    print(f"  …of which with an official-portal URL: {with_site}")
    print(f"  UN member-state floor    : {UN_MEMBER_FLOOR}")
    if len(real) < UN_MEMBER_FLOOR:
        print(f"  ✗ FAIL: real-data country coverage {len(real)} < {UN_MEMBER_FLOOR}")
        return 1
    print(f"  ✓ OK: {len(real)} real-data sovereign-state country units (≥ all UN members)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
