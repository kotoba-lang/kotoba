"""
warehouse + yard-ops cost optimizer graph.

Replaces the naive bin/door selectors in primitives.warehouse and
primitives.yard_ops with KPI-aware policies driven by the SQLMesh MVs:
  - dev.mv_dock_dwell_minutes_15m       (yard-ops dwell-time KPI)
  - dev.mv_warehouse_pick_throughput_1h (warehouse throughput KPI)

Flow:
  START → read_kpis → choose_action →
    {choose_putaway_bin | choose_dock_door | no_op}
      → emit_recommendation → END

Action shapes:
  PutawayBinDecision { skuCode, recommendedBinCode, reasoning }
  DockDoorDecision   { trailerVertexId, recommendedDockDoorCode, reasoning }

Used by:
  - warehouse.putaway.planBin  (overrides naive UUID fallback)
  - yardOps.dockDoor.select    (overrides rotating-suffix fallback)

The graph is deliberately stateless w.r.t. message history; each call is
a single decision request. Cost goal: drive avg_dwell_min and bin-spread
down over time by allocating to the historically best-performing slot.

ADR-2605080600 LangGraph Server L3.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Literal, TypedDict

from kotodama.kotoba_datomic import get_kotoba_client

LOG = logging.getLogger("warehouse_yard.optimizer")


Action = Literal["putaway_bin", "dock_door", "no_op"]


# ── State ──────────────────────────────────────────────────────────────────

class OptimizerState(TypedDict, total=False):
    # Input
    request_kind: Action      # what is being asked
    sku_code: str              # for putaway_bin
    quantity: int              # for putaway_bin
    trailer_vertex_id: str     # for dock_door
    direction: str             # 'inbound' | 'outbound'

    # KPIs (read from Datom log)
    door_dwell_stats: list[dict]   # rows from mv.dock-dwell-minutes-15m
    sku_throughput_stats: list[dict]  # rows from mv.warehouse-pick-throughput-1h

    # Output
    recommended_bin_code: str
    recommended_dock_door_code: str
    reasoning: str
    ok: bool
    error: str


# ── Node helpers ───────────────────────────────────────────────────────────

def _query(datalog_query_edn: str, args: tuple[Any, ...] = ()) -> list[list[Any]]:
    """Run a Datalog query against the kotoba client."""
    try:
        kotoba_client = get_kotoba_client()
        return kotoba_client.q(datalog_query_edn, args=args)
    except Exception as exc:
        LOG.warning("optimizer datalog query failed: %s", exc)
        return []


# ── Nodes ──────────────────────────────────────────────────────────────────

def node_read_kpis(state: OptimizerState) -> OptimizerState:
    """Read the latest dwell + throughput rows from the kotoba Datom log."""
    door_rows: list[dict] = []
    sku_rows: list[dict] = []
    
    cutoff_ts = datetime.now(timezone.utc) - timedelta(hours=24)

    if state.get("request_kind") == "dock_door":
        # R0: Fetching raw data for mv.dock-dwell-minutes-15m; aggregation done in Python.
        datalog_query_edn = """
            [:find ?dock-door-code ?avg-dwell-min ?p95-dwell-min ?completion-count ?bucket-ts
             :where
             [?e :mv.dock-dwell-minutes-15m/dock-door-code ?dock-door-code]
             [?e :mv.dock-dwell-minutes-15m/avg-dwell-min ?avg-dwell-min]
             [?e :mv.dock-dwell-minutes-15m/p95-dwell-min ?p95-dwell-min]
             [?e :mv.dock-dwell-minutes-15m/completion-count ?completion-count]
             [?e :mv.dock-dwell-minutes-15m/bucket-ts ?bucket-ts]
             [(> ?bucket-ts ?cutoff-ts)]]"""
        
        raw_results = _query(datalog_query_edn, args=(cutoff_ts,))

        # Group by dock-door-code and aggregate in Python
        grouped_data = {}
        for r in raw_results:
            dock_door_code, avg_dwell_min, p95_dwell_min, completion_count, bucket_ts = r
            if dock_door_code not in grouped_data:
                grouped_data[dock_door_code] = {
                    "avg_dwell_min_sum": 0.0,
                    "avg_dwell_min_count": 0,
                    "p95_dwell_min_sum": 0.0,
                    "p95_dwell_min_count": 0,
                    "completion_count_sum": 0,
                }
            grouped_data[dock_door_code]["avg_dwell_min_sum"] += float(avg_dwell_min or 0.0)
            grouped_data[dock_door_code]["avg_dwell_min_count"] += 1
            grouped_data[dock_door_code]["p95_dwell_min_sum"] += float(p95_dwell_min or 0.0)
            grouped_data[dock_door_code]["p95_dwell_min_count"] += 1
            grouped_data[dock_door_code]["completion_count_sum"] += int(completion_count or 0)

        for dock_door_code, aggregates in grouped_data.items():
            if aggregates["avg_dwell_min_count"] > 0:
                door_rows.append({
                    "dock_door_code": dock_door_code,
                    "avg_dwell_min": aggregates["avg_dwell_min_sum"] / aggregates["avg_dwell_min_count"],
                    "p95_dwell_min": aggregates["p95_dwell_min_sum"] / aggregates["p95_dwell_min_count"],
                    "completion_count": aggregates["completion_count_sum"],
                })
        
        # Order by avg_dwell_min ASC NULLS LAST and Limit 12
        door_rows.sort(key=lambda x: (x["avg_dwell_min"] if x["avg_dwell_min"] is not None else float('inf')))
        door_rows = door_rows[:12]

    elif state.get("request_kind") == "putaway_bin":
        sku_code_param = state.get("sku_code", "")
        # R0: Fetching raw data for mv.warehouse-pick-throughput-1h; aggregation done in Python.
        datalog_query_edn = """
            [:find ?sku-code ?picked-qty-total ?avg-bins-per-pick ?bucket-ts
             :where
             [?e :mv.warehouse-pick-throughput-1h/sku-code ?sku-code]
             [?e :mv.warehouse-pick-throughput-1h/picked-qty-total ?picked-qty-total]
             [?e :mv.warehouse-pick-throughput-1h/avg-bins-per-pick ?avg-bins-per-pick]
             [?e :mv.warehouse-pick-throughput-1h/bucket-ts ?bucket-ts]
             [(> ?bucket-ts ?cutoff-ts)]
             [?e :mv.warehouse-pick-throughput-1h/sku-code ?sku-code-param]]"""
        
        raw_results = _query(datalog_query_edn, args=(cutoff_ts, sku_code_param))

        # Group by sku-code and aggregate in Python
        grouped_data = {}
        for r in raw_results:
            sku_code, picked_qty_total, avg_bins_per_pick, bucket_ts = r
            if sku_code not in grouped_data:
                grouped_data[sku_code] = {
                    "picked_qty_total_sum": 0.0,
                    "picked_qty_total_count": 0,
                    "avg_bins_per_pick_sum": 0.0,
                    "avg_bins_per_pick_count": 0,
                }
            grouped_data[sku_code]["picked_qty_total_sum"] += float(picked_qty_total or 0.0)
            grouped_data[sku_code]["picked_qty_total_count"] += 1
            grouped_data[sku_code]["avg_bins_per_pick_sum"] += float(avg_bins_per_pick or 0.0)
            grouped_data[sku_code]["avg_bins_per_pick_count"] += 1
        
        for sku_code, aggregates in grouped_data.items():
            if aggregates["picked_qty_total_count"] > 0:
                sku_rows.append({
                    "sku_code": sku_code,
                    "picked_qty_total": aggregates["picked_qty_total_sum"] / aggregates["picked_qty_total_count"],
                    "avg_bins_per_pick": aggregates["avg_bins_per_pick_sum"] / aggregates["avg_bins_per_pick_count"],
                })
        # The original SQL had GROUP BY 1, which means no specific ORDER BY or LIMIT.
        # So, we just return the aggregated results.

    return {
        **state,
        "door_dwell_stats": door_rows,
        "sku_throughput_stats": sku_rows,
    }


def node_choose_action(state: OptimizerState) -> str:
    return state.get("request_kind", "no_op") or "no_op"


def node_choose_putaway_bin(state: OptimizerState) -> OptimizerState:
    """High-throughput SKUs go to the front-zone (BIN-A-...).
    Low-throughput SKUs go to the back-zone (BIN-C-...). This minimizes
    pick travel distance — proxy for warehouse cost."""
    sku = state.get("sku_code", "") or "NEW"
    stats = state.get("sku_throughput_stats") or []
    picked = stats[0]["picked_qty_total"] if stats else 0.0
    if picked >= 100:
        zone = "A"
        reasoning = f"SKU {sku} picked_qty_total={picked:.0f}/24h ≥100 → front-zone A"
    elif picked >= 10:
        zone = "B"
        reasoning = f"SKU {sku} picked_qty_total={picked:.0f}/24h ≥10 → mid-zone B"
    else:
        zone = "C"
        reasoning = f"SKU {sku} picked_qty_total={picked:.0f}/24h <10 → back-zone C"
    suffix = uuid.uuid4().hex[:4].upper()
    return {
        **state,
        "recommended_bin_code": f"BIN-{zone}-{sku[:6]}-{suffix}",
        "reasoning": reasoning,
        "ok": True,
    }


def node_choose_dock_door(state: OptimizerState) -> OptimizerState:
    """Pick the door with the lowest 24h avg_dwell_min that has at least
    one completion sample. Cold-start fallback: rotate by suffix."""
    direction = state.get("direction", "inbound")
    door_rows = state.get("door_dwell_stats") or []
    eligible = [d for d in door_rows if d["completion_count"] >= 1]
    if eligible:
        best = min(eligible, key=lambda d: d["avg_dwell_min"])
        reasoning = (
            f"door {best['dock_door_code']} avg_dwell={best['avg_dwell_min']:.1f}min "
            f"p95={best['p95_dwell_min']:.1f}min n={best['completion_count']} → "
            f"lowest dwell among {len(eligible)} eligible doors"
        )
        return {
            **state,
            "recommended_dock_door_code": best["dock_door_code"],
            "reasoning": reasoning,
            "ok": True,
        }
    suffix = uuid.uuid4().hex[:2].upper()
    return {
        **state,
        "recommended_dock_door_code": f"DOOR-{direction[:2].upper()}-{suffix}",
        "reasoning": f"cold-start: no dwell samples in 24h, fallback rotation",
        "ok": True,
    }


def node_no_op(state: OptimizerState) -> OptimizerState:
    return {
        **state,
        "ok": False,
        "reasoning": f"unknown request_kind={state.get('request_kind')!r}",
        "error": "unknown_request_kind",
    }


def node_emit_recommendation(state: OptimizerState) -> OptimizerState:
    """Hook for OCEL audit; in practice the BPMN audit task already
    captures the decision. Kept as a no-op pass-through."""
    return state


# ── Graph build ────────────────────────────────────────────────────────────

def build_graph():
    """Construct the optimizer LangGraph.

    Imported lazily by LangServer primitives so the LangServer worker doesn't pay
    LangGraph import cost at module load.
    """
    from langgraph.graph import StateGraph, END

    g = StateGraph(OptimizerState)
    g.add_node("read_kpis", node_read_kpis)
    g.add_node("choose_putaway_bin", node_choose_putaway_bin)
    g.add_node("choose_dock_door", node_choose_dock_door)
    g.add_node("no_op", node_no_op)
    g.add_node("emit_recommendation", node_emit_recommendation)

    g.set_entry_point("read_kpis")
    g.add_conditional_edges(
        "read_kpis",
        node_choose_action,
        {
            "putaway_bin": "choose_putaway_bin",
            "dock_door": "choose_dock_door",
            "no_op": "no_op",
        },
    )
    g.add_edge("choose_putaway_bin", "emit_recommendation")
    g.add_edge("choose_dock_door", "emit_recommendation")
    g.add_edge("no_op", "emit_recommendation")
    g.add_edge("emit_recommendation", END)
    return g.compile()


# ── Convenience wrappers (for primitives) ──────────────────────────────────

def recommend_putaway_bin(sku_code: str, quantity: int = 0) -> dict:
    """Synchronous wrapper used from warehouse.putaway.planBin."""
    try:
        graph = build_graph()
        out = graph.invoke({
            "request_kind": "putaway_bin",
            "sku_code": sku_code,
            "quantity": int(quantity or 0),
        })
        return {
            "ok": bool(out.get("ok")),
            "bin_code": out.get("recommended_bin_code", ""),
            "reasoning": out.get("reasoning", ""),
        }
    except Exception as exc:
        LOG.warning("recommend_putaway_bin failed: %s", exc)
        return {"ok": False, "bin_code": "", "reasoning": str(exc)}


def recommend_dock_door(trailer_vertex_id: str, direction: str = "inbound") -> dict:
    """Synchronous wrapper used from yardOps.dockDoor.select."""
    try:
        graph = build_graph()
        out = graph.invoke({
            "request_kind": "dock_door",
            "trailer_vertex_id": trailer_vertex_id,
            "direction": direction,
        })
        return {
            "ok": bool(out.get("ok")),
            "dock_door_code": out.get("recommended_dock_door_code", ""),
            "reasoning": out.get("reasoning", ""),
        }
    except Exception as exc:
        LOG.warning("recommend_dock_door failed: %s", exc)
        return {"ok": False, "dock_door_code": "", "reasoning": str(exc)}
