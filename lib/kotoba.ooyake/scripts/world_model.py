#!/usr/bin/env python3
"""world_model.py — CLI for ooyake's cross-actor WORLD-MODEL reconcile.

Thin wrapper over cells/world_model/cell.py (single source of truth). Joins the
ooyake structural atlas (:gov.unit/*) to the tsumugi karma graph (:organism/*)
over the shared :gov.unit/organism id-space, OFFLINE + deterministic, and prints
a reconcile report. Optionally writes the world-model artifact EDN.

LIVE planet-scale reconcile + write-back is Council + operator gated (see
WorldModelCell). This is the read-side proposal (G9).

Usage:
    python3 world_model.py                    # print report
    python3 world_model.py --edn out/         # also write out/world-model.kotoba.edn
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "cells", "world_model")))
from cell import WorldModelCell  # noqa: E402


def main() -> int:
    out_dir = None
    if "--edn" in sys.argv:
        out_dir = sys.argv[sys.argv.index("--edn") + 1]
    rep = WorldModelCell().solve({"mode": "bundled", "out_dir": out_dir})["report"]
    if "--entity" in sys.argv:
        from cell import regulators_of  # noqa: E402
        ent = sys.argv[sys.argv.index("--entity") + 1]
        regs = regulators_of(rep, ent)
        print(f"world-model regulators of {ent}: {len(regs)}")
        for r in regs:
            print(f"  {r['gov_unit']}  ({r['kind']})")
        return 0
    cov = rep["coverage"]
    print("ooyake ↔ tsumugi world-model reconcile (bundled offline, ADR-2606021600 §3)")
    print(f"  gov units (structure)         : {rep['gov_units_total']}")
    print(f"  organisms (karma graph)       : {rep['organisms_total']}")
    print(f"  power-bearing units           : {rep['power_bearing_units']}")
    print(f"  excluded (civic surface/local): {rep['excluded_non_power_units']}")
    print(f"  → CONFIRMED links (explicit)  : {len(rep['confirmed_links'])}  "
          f"{[r['unit'] + '→' + r['organism'] for r in rep['confirmed_links']]}")
    print(f"  → DERIVED links (id match)    : {len(rep['derived_links'])}")
    print(f"  → DANGLING links (G5 flag)    : {len(rep['dangling_links'])}")
    print(f"  → PROPOSED links (latent)     : {len(rep['proposed_links'])}")
    print(f"  orphan gov organisms (in karma, not in atlas): "
          f"{len(rep['orphan_gov_organisms'])}  {rep['orphan_gov_organisms']}")
    print(f"  non-gov organisms (out of atlas scope, ok): {rep['non_gov_organisms_out_of_atlas']}")
    print(f"  reconciled: {cov['reconciled_pct']}% ({cov['reconciled']}/{rep['power_bearing_units']}) "
          f"[rest honestly :proposed/:representative, G5]")
    stew = rep.get("government_stewardship", [])
    print(f"  → GOVERNMENT STEWARDSHIP paths (gov.unit → entity): {len(stew)}")
    for s in stew:
        print(f"      {s['gov_unit']}  --{s['kind']}-->  {s['entity_label']} ({s['entity']})")
    if out_dir:
        print(f"  wrote {os.path.join(out_dir, 'world-model.kotoba.edn')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
