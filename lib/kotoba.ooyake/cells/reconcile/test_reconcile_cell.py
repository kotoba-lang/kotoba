"""Tests for ooyake ReconcileCell (ADR-2606021600 §5).

Run: python3 -m pytest cells/reconcile/test_reconcile_cell.py
 or: python3 cells/reconcile/test_reconcile_cell.py  (self-run)
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cell import ReconcileCell, reconcile  # noqa: E402


def test_bundled_promotes_expected_units():
    rep = reconcile()
    # full JP central + proof-of-model chain + breadth rows
    assert rep["total_units"] == 28, rep["total_units"]
    # exactly the 8 units present in authority-reference.edn, all agreeing
    assert rep["coverage"]["authoritative_after"] == 8
    assert rep["promoted_to_authoritative"] == [
        "gov.gbr.hmrc",
        "gov.jpn",
        "gov.jpn.cao",
        "gov.jpn.meti",
        "gov.jpn.mof",
        "gov.jpn.mofa",
        "gov.jpn.pref.13",
        "gov.usa.treasury",
    ]


def test_no_conflicts_and_honest_remainder():
    rep = reconcile()
    assert rep["conflicts_kept_unverified"] == []
    # everything without an authority record stays representative (G5)
    assert len(rep["no_authority_record_kept_representative"]) == 20
    assert rep["coverage"]["representative_after"] == 20


def test_cell_bundled_mode_ok():
    out = ReconcileCell().solve({"mode": "bundled"})
    assert out["status"] == "ok"
    assert out["report"]["coverage"]["authoritative_after"] == 8


def test_cell_live_mode_gated():
    try:
        ReconcileCell().solve({"mode": "live"})
    except RuntimeError as e:
        assert "G4" in str(e) and "not activated" in str(e)
    else:
        raise AssertionError("live mode must raise (G4 gated)")


def test_cell_unknown_mode_rejected():
    try:
        ReconcileCell().solve({"mode": "bogus"})
    except ValueError as e:
        assert "unknown reconcile mode" in str(e)
    else:
        raise AssertionError("unknown mode must raise ValueError")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"{len(fns)} passed")
