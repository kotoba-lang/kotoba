#!/usr/bin/env python3
"""g20_coverage.py — ooyake REAL-DATA G20 coverage report (founder directive
2026-06-03 "demo じゃなくて実データ, G20").

Unlike the reconcile DEMO (which proves the :representative→:authoritative promotion
mechanism on a bundled fixture), this reports ACTUAL committed coverage of the G20
from the registry seeds: for each G20 member, is there a country unit AND a finance
ministry/treasury, both :authoritative + :maintainer-verified (real data, QID
web-verified, provenance = the body's own official URL)?

READ-ONLY. Exits non-zero if any G20 member is missing its country or finance unit,
or if any present G20 row is not real-data tier — doubles as a CI gate that the G20
set stays complete + authoritative.

Usage: python3 g20_coverage.py
"""
from __future__ import annotations

import glob
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "cells", "reconcile")))
from cell import parse_edn  # noqa: E402

_REG = os.path.normpath(os.path.join(_HERE, "..", "registry"))

# G20: 19 sovereign members + the EU.
#   (name, country id, finance ministry id|None for EU, central bank id)
G20 = [
    ("Japan", "gov.jpn", "gov.jpn.mof", "gov.jpn.boj"),
    ("United States", "gov.usa", "gov.usa.treasury", "gov.usa.fed"),
    ("United Kingdom", "gov.gbr", "gov.gbr.hmrc", "gov.gbr.boe"),
    ("France", "gov.fra", "gov.fra.minefi", "gov.fra.banque"),
    ("Germany", "gov.deu", "gov.deu.bmf", "gov.deu.bundesbank"),
    ("Italy", "gov.ita", "gov.ita.mef", "gov.ita.bancaditalia"),
    ("Canada", "gov.can", "gov.can.fin", "gov.can.boc"),
    ("China", "gov.chn", "gov.chn.mof", "gov.chn.pbc"),
    ("Brazil", "gov.bra", "gov.bra.fazenda", "gov.bra.bcb"),
    ("Russia", "gov.rus", "gov.rus.minfin", "gov.rus.cbr"),
    ("Mexico", "gov.mex", "gov.mex.shcp", "gov.mex.banxico"),
    ("Indonesia", "gov.idn", "gov.idn.kemenkeu", "gov.idn.bi"),
    ("Türkiye", "gov.tur", "gov.tur.hmb", "gov.tur.tcmb"),
    ("South Africa", "gov.zaf", "gov.zaf.treasury", "gov.zaf.sarb"),
    ("Argentina", "gov.arg", "gov.arg.economia", "gov.arg.bcra"),
    ("Saudi Arabia", "gov.sau", "gov.sau.mof", "gov.sau.sama"),
    ("South Korea", "gov.kor", "gov.kor.moef", "gov.kor.bok"),
    ("India", "gov.ind", "gov.ind.mof", "gov.ind.rbi"),
    ("Australia", "gov.aus", "gov.aus.treasury", "gov.aus.rba"),
    ("European Union", "gov.eu", None, "gov.eu.ecb"),
]


def load_all() -> dict[str, dict]:
    units: dict[str, dict] = {}
    for f in sorted(glob.glob(os.path.join(_REG, "gov-units*.edn"))):
        for u in parse_edn(open(f, encoding="utf-8").read()).get(":units", []):
            if u.get(":gov.unit/id"):
                units[u[":gov.unit/id"]] = u
    return units


def _real(u) -> bool:
    return (u is not None
            and u.get(":gov.unit/sourcing") == ":authoritative"
            and u.get(":gov.unit/verification-status") == ":maintainer-verified"
            and bool(u.get(":gov.unit/wikidata")))


def main() -> int:
    units = load_all()
    errors: list[str] = []
    full = 0
    print("ooyake REAL-DATA G20 coverage (committed registry; not the reconcile demo)")
    for name, cid, fid, bid in G20:
        c = units.get(cid)
        f = units.get(fid) if fid else None
        b = units.get(bid)
        c_ok = _real(c)
        f_ok = _real(f) if fid else True
        b_ok = _real(b)
        if c_ok and f_ok and b_ok:
            full += 1
        mark = "✓" if (c_ok and f_ok and b_ok) else "✗"
        print(f"  {mark} {name:14} country={'OK' if c_ok else 'MISSING':7} "
              f"finance={('OK' if f_ok else ('n/a' if not fid else 'MISSING')):7} "
              f"central-bank={'OK' if b_ok else 'MISSING'}")
        if not c_ok:
            errors.append(f"{name}: country {cid} not real-data")
        if fid and not f_ok:
            errors.append(f"{name}: finance {fid} not real-data")
        if not b_ok:
            errors.append(f"{name}: central bank {bid} not real-data")
    print(f"\n  G20 members fully covered (country + finance + central bank, real-data): {full}/{len(G20)}")
    if errors:
        print("  INCOMPLETE:")
        for e in errors:
            print(f"    ✗ {e}")
        return 1
    print("  ALL G20 members present as real (:authoritative + :maintainer-verified) data.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
