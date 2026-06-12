"""Tests for junkan CLD auto-discovery + passive dry-run (ADR-2605290927)."""

from __future__ import annotations

from pathlib import Path

import pytest

from kotodama.organism.junkan import (
    StockSeries,
    discover_loops,
    find_cycles,
    infer_adjacency,
    load_fixture,
    run_analysis,
    series_from_observations,
)

FIXTURE = Path(__file__).parent / "fixtures" / "junkan_netreg_dry_run.json"


# ── CLD auto-discovery ──────────────────────────────────────────────────────
def test_find_cycles_dedupes_two_cycle():
    adj = {"a": {"b"}, "b": {"a"}}
    cycles = find_cycles(adj, max_len=3)
    assert cycles == [["a", "b"]]  # reported once, from smallest member


def test_infer_adjacency_thresholds_low_confidence():
    # a flat (zero-variance) stock yields no edges (G5 abstain)
    series = [
        StockSeries("a", [1, 2, 3, 4], "u", 1, "cid"),
        StockSeries("flat", [5, 5, 5, 5], "u", 1, "cid"),
    ]
    adj = infer_adjacency(series, min_conf=0.5, lag=0)
    assert adj["flat"] == set() and adj["a"] == set()


def test_discover_loops_finds_reinforcing_pair():
    # two anti-correlated rising/falling stocks form a 2-cycle
    series = [
        StockSeries("conc", [40, 44, 49, 55, 62], "bp", -1, "cid"),
        StockSeries("share", [60, 56, 51, 45, 38], "bp", 1, "cid"),
    ]
    specs = discover_loops(series, min_conf=0.6, max_len=3, lag=1)
    assert len(specs) == 1
    assert set(specs[0].stock_cycle) == {"conc", "share"}


def test_run_analysis_auto_mode_classifies_discovered_loop():
    series = [
        StockSeries("conc", [40, 44, 49, 55, 62], "bp", -1, "cid"),
        StockSeries("share", [60, 56, 51, 45, 38], "bp", 1, "cid"),
    ]
    bundle = run_analysis(series, auto=True, min_conf=0.6)
    assert bundle.discovered_loop_ids  # CLD discovered at least one loop
    assert len(bundle.causal_loop_findings) == 1
    f = bundle.causal_loop_findings[0]
    assert f["loopType"] == "reinforcing"
    assert f["currentRegime"] == "vicious"


# ── passive dry-run on a Tier-A-shaped fixture ──────────────────────────────
def test_dry_run_g3_requires_source_cid():
    with pytest.raises(ValueError, match="source_cid"):
        series_from_observations([{"stock_id": "x", "level": 1, "unit": "u"}])


def test_dry_run_g6_rejects_individual_field():
    with pytest.raises(ValueError, match="aggregate-only"):
        series_from_observations(
            [{"stock_id": "x", "level": 1, "unit": "u", "source_cid": "c", "person_id": "alice"}]
        )


def test_dry_run_fixture_detects_vicious_concentration_loop():
    series = load_fixture(FIXTURE)
    # every series carries passive-archive provenance (G3)
    assert all(s.source_cid for s in series)
    bundle = run_analysis(series, auto=True, min_conf=0.6, max_len=3)

    # the flat IANA control stock must NOT appear in any discovered loop
    loop_members = {sid for f in bundle.causal_loop_findings for e in f["edges"] for sid in (e["fromStockId"], e["toStockId"])}
    assert "iana-tld-delegation-openness" not in loop_members

    # the concentration<->smallholder-share pair is a vicious reinforcing loop
    assert bundle.causal_loop_findings, "expected at least one discovered loop"
    vicious = [f for f in bundle.causal_loop_findings if f["currentRegime"] == "vicious"]
    assert vicious
    f = vicious[0]
    assert f["loopType"] == "reinforcing"
    assert f["dominantStockId"] in {"rir-ipv4-allocation-concentration", "smallholder-routable-address-share"}
    assert f["actuationTaken"] is False  # G4: dry-run produced analysis only
