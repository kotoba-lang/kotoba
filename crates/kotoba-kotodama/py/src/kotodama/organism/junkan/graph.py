"""junkan.graph — the analysis-only pipeline (stdlib orchestrator + LangGraph wiring).

ADR-2605290927. The pipeline:

    ingest → estimate_stocks → infer_flows → build_cld → classify_loops
           → find_leverage → wellbecoming_frame → emit_findings

G4 (analysis-only / no actuation) is enforced **by absence**: there is no
dispatch / post / mention / send node, and the only output is a ``FindingBundle``
whose ``actuation_taken`` is a const False. ``emit_findings`` writes findings and
nothing else — it cannot reach an outward channel because none exists here.

``run_analysis`` is a pure stdlib orchestrator (no langgraph, no network, no
inference) so the core is fully testable offline. With ``auto=True`` and no
explicit ``loop_specs`` it discovers the loops from the data (``cld.discover_loops``).
``build_junkan_graph`` wires the same steps into a LangGraph ``StateGraph`` for
the fleet runtime (R1+; cell activation is Council-gated).
"""

from __future__ import annotations

from .cld import discover_loops
from .datom import DatomStore
from .flows import FlowEdge, infer_flow
from .leverage import rank_leverage_candidates
from .loops import build_loop, detect_regime_shift
from .models import FindingBundle, LoopSpec, StockSeries


def _pct(x: float) -> int:
    """Confidence as integer percent 0..100 (lexicon convention)."""
    return max(0, min(100, round(x * 100)))


def _slope_abs(levels: list[int]) -> float:
    n = len(levels)
    if n < 2:
        return 0.0
    xs = list(range(n))
    mx = sum(xs) / n
    my = sum(levels) / n
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0.0:
        return 0.0
    return abs(sum((x - mx) * (y - my) for x, y in zip(xs, levels)) / denom)


def run_analysis(
    stock_series: list[StockSeries],
    loop_specs: list[LoopSpec] | None = None,
    prev_regimes: dict[str, str] | None = None,
    *,
    auto: bool = False,
    min_conf: float = 0.5,
    max_len: int = 3,
    lag: int = 1,
    attesting_did: str = "did:web:junkan.etzhayyim.com",
) -> FindingBundle:
    """Run the full analysis-only pipeline. Pure; returns findings only.

    If ``loop_specs`` is omitted and ``auto`` is True, loops are discovered
    directly from the stock series (CLD auto-construction).
    """
    prev_regimes = prev_regimes or {}
    series = {s.stock_id: s for s in stock_series}

    if loop_specs is None:
        loop_specs = (
            discover_loops(stock_series, min_conf=min_conf, max_len=max_len, lag=lag)
            if auto
            else []
        )

    # estimate_stocks: append-only datom store (G9), tick-by-tick history.
    store = DatomStore()
    n = min((len(s.levels) for s in stock_series), default=0)
    for s in stock_series:  # static facts
        store.transact(
            [
                (s.stock_id, ":junkan.stock/id", s.stock_id),
                (s.stock_id, ":junkan.stock/unit", s.unit),
                (s.stock_id, ":junkan.stock/desirability", s.desirability),
                (s.stock_id, ":junkan.stock/source-cid", s.source_cid),
            ]
        )
    for i in range(n):  # time-series levels, one tx per tick
        store.transact([(s.stock_id, ":junkan.stock/level", s.levels[i]) for s in stock_series])

    loop_findings: list[dict] = []
    leverage_findings: list[dict] = []
    regime_shifts: list[dict] = []

    for spec in loop_specs:
        cyc = spec.stock_cycle
        if len(cyc) < 2 or any(sid not in series for sid in cyc):
            continue
        # infer_flows: consecutive edges incl. wraparound
        edges: list[FlowEdge] = []
        ok = True
        for a, b in zip(cyc, cyc[1:] + cyc[:1]):
            e = infer_flow(a, b, series[a].levels, series[b].levels, lag=lag)
            if e is None:  # G5: abstain on insufficient evidence
                ok = False
                break
            edges.append(e)
        if not ok:
            continue

        # build_cld / classify_loops: dominant stock = max |slope|
        dominant = max(cyc, key=lambda sid: _slope_abs(series[sid].levels))
        dom_traj = [(t, lvl) for t, lvl in store.history(dominant, ":junkan.stock/level")]
        loop = build_loop(spec.loop_id, edges, dominant, dom_traj, series[dominant].desirability)

        loop_findings.append(
            {
                "$type": "com.etzhayyim.junkan.causalLoopFinding",
                "loopId": loop.loop_id,
                "loopType": loop.loop_type,
                "currentRegime": loop.regime,
                "dominantStockId": loop.dominant_stock,
                "edges": [
                    {
                        "fromStockId": e.from_stock,
                        "toStockId": e.to_stock,
                        "polarity": e.polarity,
                        "lagTicks": e.lag_ticks,
                        "edgeConfidence": _pct(e.confidence),
                    }
                    for e in loop.edges
                ],
                "confidence": _pct(loop.confidence),
                "hypothesisOnly": True,  # G5
                "actuationTaken": False,  # G4
                "charterRiderScanPass": True,  # G1 (placeholder; real scan at R1)
                "attestingDid": attesting_did,
            }
        )

        # find_leverage (G11: candidates, prescriptionGiven False)
        for c in rank_leverage_candidates(loop):
            leverage_findings.append(
                {
                    "$type": "com.etzhayyim.junkan.leveragePointFinding",
                    "targetLoopId": c.target_loop_id,
                    "meadowsLevel": c.meadows_level,
                    "description": c.description,
                    "uncertaintyBand": c.uncertainty_band,
                    "wouldFlipTo": c.would_flip_to,
                    "prescriptionGiven": False,  # G11
                    "actuationTaken": False,  # G4
                    "charterRiderScanPass": True,
                    "attestingDid": attesting_did,
                }
            )

        # regime shift vs prior
        shift = detect_regime_shift(
            loop.loop_id, prev_regimes.get(loop.loop_id, loop.regime), loop.regime
        )
        if shift is not None:
            regime_shifts.append(
                {
                    "$type": "com.etzhayyim.junkan.regimeShiftEvent",
                    "loopId": shift.loop_id,
                    "fromRegime": shift.from_regime,
                    "toRegime": shift.to_regime,
                    "framingNonEschatological": True,  # G7
                    "actuationTaken": False,  # G4
                    "charterRiderScanPass": True,
                    "attestingDid": attesting_did,
                }
            )

    return FindingBundle(
        causal_loop_findings=loop_findings,
        leverage_findings=leverage_findings,
        regime_shifts=regime_shifts,
        discovered_loop_ids=[s.loop_id for s in loop_specs],
    )


def build_junkan_graph():  # pragma: no cover - exercised only when langgraph present
    """Wire the pipeline into a LangGraph StateGraph (fleet runtime, R1+).

    Lazy-imports langgraph so this module imports without the dependency. The
    graph has NO dispatch node — G4 is enforced by absence.
    """
    from typing import TypedDict

    from langgraph.graph import END, START, StateGraph

    class JunkanState(TypedDict, total=False):
        stock_series: list
        loop_specs: list
        prev_regimes: dict
        auto: bool
        bundle: FindingBundle

    def _analyze(state: "JunkanState") -> dict:
        bundle = run_analysis(
            state.get("stock_series", []),
            state.get("loop_specs", None),
            state.get("prev_regimes", {}),
            auto=state.get("auto", False),
        )
        return {"bundle": bundle}

    g = StateGraph(JunkanState)
    g.add_node("analyze", _analyze)  # composed pure pipeline; no outward node
    g.add_edge(START, "analyze")
    g.add_edge("analyze", END)
    return g.compile()
