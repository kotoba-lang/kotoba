#!/usr/bin/env python3
"""world_model_coverage.py — regression gate for the cross-actor world-model reconcile.

Asserts the ooyake↔tsumugi reconcile (cells/world_model/) stays healthy over the
REAL committed registry + tsumugi seed:

  - the reconcile runs offline and classifies the atlas;
  - the one wired link (gov.jpn.meti ↔ org.state.jp.meti) stays CONFIRMED;
  - there are ZERO dangling links (every explicit :gov.unit/organism resolves — G5);
  - civic service surface is EXCLUDED (power-only, never a target-list — G1/G10);
  - the generated world-model artifact is well-formed (balanced EDN).

READ-ONLY. Exits non-zero if any invariant regresses. This is the maturity gate
that lets coverage GROW (more confirmed links) without silently breaking the
honesty invariants. Run by deploy/run_tests.sh.

Usage: python3 world_model_coverage.py [--quiet]
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "cells", "world_model")))
from cell import (  # noqa: E402
    load_edges,
    load_gov_units,
    load_organisms,
    reconcile_world_model,
    render_world_model_edn,
)

# floors: regression guards, NOT precise claims. confirmed may only GROW.
CONFIRMED_FLOOR = 9
POWER_UNITS_FLOOR = 100
# the wired :gov.unit/organism links that MUST stay confirmed (documented bodies)
EXPECTED_CONFIRMED = {
    "gov.jpn.meti",        # → org.state.jp.meti
    "gov.jpn.finreg",      # FSA → org.state.jp.fsa
    "gov.jpn.boj",         # Bank of Japan → org.state.jp.boj
    "gov.usa.sec",         # US SEC → org.state.us.sec
    "gov.usa.fed",         # Federal Reserve → org.state.us.fed
    "gov.eu",              # European Union → org.state.eu
    "gov.gbr.competition",  # UK CMA → org.state.uk.cma
    "gov.usa.competition",  # US DOJ Antitrust → org.state.us.doj-antitrust
    "gov.jpn.competition",  # JFTC → org.state.jp.jftc
}


STEWARDSHIP_FLOOR = 10  # cross-graph gov→entity paths the world model must resolve


def main() -> int:
    quiet = "--quiet" in sys.argv
    gov = load_gov_units()
    orgs = load_organisms()
    edges = load_edges()
    r = reconcile_world_model(gov, orgs, edges)
    edn = render_world_model_edn(r)

    checks: list[tuple[str, bool, str]] = []
    confirmed_units = {c["unit"] for c in r["confirmed_links"]}
    missing = EXPECTED_CONFIRMED - confirmed_units
    checks.append((
        "all wired links confirmed",
        missing == set(),
        f"missing={sorted(missing)}" if missing else "meti/fsa/boj/sec all reconcile",
    ))
    checks.append((
        f"confirmed ≥ {CONFIRMED_FLOOR}",
        len(r["confirmed_links"]) >= CONFIRMED_FLOOR,
        f"confirmed={len(r['confirmed_links'])}",
    ))
    checks.append((
        "no dangling links (G5)",
        r["dangling_links"] == [],
        f"dangling={r['dangling_links']}",
    ))
    stew = r.get("government_stewardship", [])
    checks.append((
        f"stewardship paths ≥ {STEWARDSHIP_FLOOR}",
        len(stew) >= STEWARDSHIP_FLOOR,
        f"paths={len(stew)}",
    ))
    checks.append((
        "stewardship gov-units all reconciled",
        all(s["gov_unit"] in confirmed_units or s["gov_unit"] in {d["unit"] for d in r["derived_links"]} for s in stew),
        "every stewardship path originates at a reconciled unit",
    ))
    checks.append((
        f"power-bearing units ≥ {POWER_UNITS_FLOOR}",
        r["power_bearing_units"] >= POWER_UNITS_FLOOR,
        f"power={r['power_bearing_units']}",
    ))
    checks.append((
        "civic surface excluded (G1/G10)",
        r["excluded_non_power_units"] > 0,
        f"excluded={r['excluded_non_power_units']}",
    ))
    checks.append((
        "no orphan gov organisms",
        r["orphan_gov_organisms"] == [],
        f"orphans={r['orphan_gov_organisms']}",
    ))
    checks.append((
        "world-model EDN well-formed",
        edn.count("{") == edn.count("}") and "world-model-v1" in edn,
        "balanced braces + graph header",
    ))

    failed = [c for c in checks if not c[1]]
    if not quiet:
        cov = r["coverage"]
        print("ooyake world-model reconcile coverage gate")
        print(f"  power-bearing units : {r['power_bearing_units']}  (excluded {r['excluded_non_power_units']})")
        print(f"  confirmed / proposed: {len(r['confirmed_links'])} / {len(r['proposed_links'])}")
        print(f"  reconciled          : {cov['reconciled_pct']}% ({cov['reconciled']}/{r['power_bearing_units']})")
        for label, ok, detail in checks:
            print(f"  {'✓' if ok else '✗'} {label}  [{detail}]")
    if failed:
        print(f"  ✗ FAIL: {len(failed)} world-model invariant(s) regressed")
        return 1
    if not quiet:
        print("  ✓ OK: all world-model invariants hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
