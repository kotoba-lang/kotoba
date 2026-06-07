"""Tests for kotodama.organism.junkan (ADR-2605290927).

Covers the analysis-only core: append-only datom store + time-travel, flow
polarity inference, virtuous/vicious regime read-off, Meadows leverage
candidates, the end-to-end run_analysis pipeline, and the G4 (no-actuation) /
G5 / G6 / G9 / G11 structural invariants.
"""

from __future__ import annotations

import importlib

import pytest

from kotodama.organism import junkan
from kotodama.organism.junkan import (
    DatomStore,
    FindingBundle,
    LoopSpec,
    StockObservation,
    StockSeries,
    build_loop,
    classify_regime,
    detect_regime_shift,
    infer_flow,
    loop_polarity,
    rank_leverage_candidates,
    record_stock,
    run_analysis,
    trajectory,
)
from kotodama.organism.junkan.flows import FlowEdge


# ── datom store: append-only + time-travel ────────────────────────────────
def test_datom_history_and_as_of():
    s = DatomStore()
    s.transact([("gini", ":junkan.stock/level", 30)])
    s.transact([("gini", ":junkan.stock/level", 34)])
    t3 = s.transact([("gini", ":junkan.stock/level", 41)])
    assert s.history("gini", ":junkan.stock/level") == [(1, 30), (2, 34), (3, 41)]
    # as-of time-travel: value as of tx 2 is 34, not the latest 41
    assert s.entity("gini", as_of=2)[":junkan.stock/level"] == 34
    assert s.entity("gini")[":junkan.stock/level"] == 41
    assert t3 == s.basis_t == 3


def test_datom_find_avet():
    s = DatomStore()
    s.transact([("loopA", ":junkan.loop/regime", "vicious")])
    s.transact([("loopB", ":junkan.loop/regime", "virtuous")])
    assert s.find(":junkan.loop/regime", "vicious") == ["loopA"]


def test_datom_no_retraction_api():
    # G9: append-only — there is intentionally no retract method.
    assert not hasattr(DatomStore, "retract")


# ── stocks: G6 aggregate-only ──────────────────────────────────────────────
def test_record_stock_and_trajectory():
    s = DatomStore()
    record_stock(s, StockObservation("gini", 30, "bp", "2026-01-01T00:00Z", "bafyA", desirability=-1))
    record_stock(s, StockObservation("gini", 35, "bp", "2026-02-01T00:00Z", "bafyB", desirability=-1))
    assert trajectory(s, "gini") == [(1, 30), (2, 35)]


def test_record_stock_rejects_individual_field():
    s = DatomStore()
    with pytest.raises(ValueError, match="aggregate-only"):
        record_stock(s, StockObservation("x", 1, "u", "t", "cid"), person_id="alice")  # type: ignore[arg-type]


# ── flows: hypothesis-only polarity ────────────────────────────────────────
def test_infer_flow_positive_and_negative():
    pos = infer_flow("a", "b", [1, 2, 3, 4], [1, 2, 3, 4], lag=0)
    assert pos is not None and pos.polarity == "pos"
    neg = infer_flow("a", "b", [1, 2, 3, 4], [4, 3, 2, 1], lag=0)
    assert neg is not None and neg.polarity == "neg"


def test_infer_flow_abstains_on_flat_series():
    # zero variance → no claim (G5: abstain rather than overclaim)
    assert infer_flow("a", "b", [5, 5, 5], [1, 2, 3], lag=0) is None


# ── loops: polarity + regime ───────────────────────────────────────────────
def test_loop_polarity_reinforcing_even_negatives():
    e = lambda p: FlowEdge("a", "b", p, 1, 0.9)  # noqa: E731
    assert loop_polarity([e("neg"), e("neg")]) == "reinforcing"  # 2 neg → R
    assert loop_polarity([e("pos"), e("pos")]) == "reinforcing"  # 0 neg → R
    assert loop_polarity([e("neg"), e("pos")]) == "balancing"  # 1 neg → B


def test_classify_regime_vicious_and_virtuous():
    rising = [(1, 30), (2, 34), (3, 38), (4, 43)]
    # lower-is-better stock rising in a reinforcing loop → vicious (悪循環)
    assert classify_regime(rising, "reinforcing", desirability=-1) == "vicious"
    # higher-is-better stock rising in a reinforcing loop → virtuous (好循環)
    assert classify_regime(rising, "reinforcing", desirability=1) == "virtuous"


def test_classify_regime_transitioning_and_neutral():
    flip = [(1, 10), (2, 14), (3, 11), (4, 6)]  # up then down
    assert classify_regime(flip, "reinforcing", desirability=1) == "transitioning"
    flat = [(1, 10), (2, 10), (3, 10)]
    assert classify_regime(flat, "reinforcing", desirability=1) == "neutral"


def test_detect_regime_shift():
    assert detect_regime_shift("L", "virtuous", "virtuous") is None
    sh = detect_regime_shift("L", "virtuous", "vicious")
    assert sh is not None and sh.from_regime == "virtuous" and sh.to_regime == "vicious"


# ── leverage: G11 no prescription ──────────────────────────────────────────
def test_leverage_candidates_never_prescribe():
    loop = build_loop(
        "L", [FlowEdge("a", "b", "neg", 1, 0.8), FlowEdge("b", "a", "neg", 1, 0.8)],
        "a", [(1, 30), (2, 40)], desirability=-1,
    )
    cands = rank_leverage_candidates(loop)
    assert cands and all(c.prescription_given is False for c in cands)
    # deepest-leverage-first ordering
    assert [c.meadows_level for c in cands] == sorted(c.meadows_level for c in cands)


# ── end-to-end: a vicious cycle and a virtuous cycle ───────────────────────
def test_run_analysis_detects_vicious_cycle():
    # inequality ↑ → opportunity-access ↓ → inequality ↑  (two neg links → R)
    inequality = StockSeries("inequality", [30, 34, 39, 45, 52], "gini-bp", -1, "bafy-ineq")
    opportunity = StockSeries("opportunity", [70, 66, 60, 53, 45], "idx", 1, "bafy-opp")
    bundle = run_analysis(
        [inequality, opportunity],
        [LoopSpec("inequality-trap", ["inequality", "opportunity"])],
        prev_regimes={"inequality-trap": "neutral"},
    )
    assert isinstance(bundle, FindingBundle)
    assert len(bundle.causal_loop_findings) == 1
    f = bundle.causal_loop_findings[0]
    assert f["loopType"] == "reinforcing"
    assert f["currentRegime"] == "vicious"  # 悪循環
    assert f["hypothesisOnly"] is True and f["actuationTaken"] is False
    assert 0 <= f["confidence"] <= 100
    # regime shift neutral → vicious recorded
    assert bundle.regime_shifts and bundle.regime_shifts[0]["toRegime"] == "vicious"
    # leverage candidates present, none prescriptive
    assert bundle.leverage_findings
    assert all(lf["prescriptionGiven"] is False for lf in bundle.leverage_findings)


def test_run_analysis_detects_virtuous_cycle():
    # open-data ↑ → civic-participation ↑ → open-data ↑  (zero neg links → R)
    opendata = StockSeries("open-data", [40, 48, 57, 67], "pct", 1, "bafy-od")
    civic = StockSeries("civic", [20, 27, 35, 44], "pct", 1, "bafy-civ")
    bundle = run_analysis(
        [opendata, civic],
        [LoopSpec("civic-flywheel", ["open-data", "civic"])],
    )
    f = bundle.causal_loop_findings[0]
    assert f["loopType"] == "reinforcing"
    assert f["currentRegime"] == "virtuous"  # 好循環


# ── G4: no outward channel anywhere in the package ─────────────────────────
def test_g4_no_outward_channel_callable():
    bundle = run_analysis([], [])
    assert bundle.actuation_taken is False
    # FindingBundle exposes no send/post/dispatch method
    assert not any(hasattr(bundle, m) for m in ("send", "post", "dispatch", "notify", "mention"))
    # the package surface exposes no outward-channel callable
    banned = ("post", "send", "dispatch", "mention", "email", "notify", "publish")
    for name in dir(junkan):
        assert not any(name.lower().startswith(b) for b in banned), name


# ── graph wiring (skips cleanly without langgraph) ─────────────────────────
def test_build_junkan_graph_runs_if_langgraph_present():
    if importlib.util.find_spec("langgraph") is None:
        pytest.skip("langgraph not installed")
    app = junkan.build_junkan_graph()
    out = app.invoke(
        {
            "stock_series": [
                StockSeries("inequality", [30, 36, 43, 51], "bp", -1, "bafy"),
                StockSeries("opportunity", [70, 63, 55, 46], "idx", 1, "bafy2"),
            ],
            "loop_specs": [LoopSpec("trap", ["inequality", "opportunity"])],
            "prev_regimes": {},
        }
    )
    assert out["bundle"].causal_loop_findings[0]["currentRegime"] == "vicious"
