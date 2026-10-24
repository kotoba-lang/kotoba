#!/usr/bin/env python3
"""reconcile.py — CLI for ooyake's R1 reconcile cell (ADR-2606021600 §5).

Thin wrapper over cells/reconcile/cell.py (single source of truth for the
reconcile logic). Runs the BUNDLED (offline, deterministic) reconcile against
registry/authority-reference.edn and prints a promotion report. LIVE fetch of
external authorities is G4 + Council + operator gated (see ReconcileCell).

Usage:
    python3 reconcile.py                 # print report
    python3 reconcile.py --json out.json # also write a machine report
"""
from __future__ import annotations

import json
import os
import sys

# import the cell core (single source of truth)
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "cells", "reconcile")))
from cell import reconcile  # noqa: E402


def main() -> int:
    rep = reconcile()
    print("ooyake reconcile (bundled offline demo, ADR-2606021600 §5)")
    print(f"  units in seed         : {rep['total_units']}")
    print(f"  authority records     : {rep['authority_records']}")
    print(f"  → PROMOTED authoritative : {len(rep['promoted_to_authoritative'])}  {rep['promoted_to_authoritative']}")
    print(f"  → conflicts (unverified) : {len(rep['conflicts_kept_unverified'])}")
    for c in rep["conflicts_kept_unverified"]:
        print(f"      ! {c['unit']}  wikidata_match={c['wikidata_match']} url_match={c['official_url_match']}")
    print(f"  → no authority (stays representative): {len(rep['no_authority_record_kept_representative'])}")
    print(
        f"  coverage: {rep['coverage']['authoritative_pct']}% authoritative "
        f"({rep['coverage']['authoritative_after']}/{rep['total_units']})  [rest honestly :representative, G5]"
    )
    if "--json" in sys.argv:
        out = sys.argv[sys.argv.index("--json") + 1]
        json.dump(rep, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"  wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
