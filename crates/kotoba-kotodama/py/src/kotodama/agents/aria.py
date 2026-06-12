"""
com.etzhayyim.signal.aria — ARIA LangGraph agent (6-signal parallel ingest + minimax).

Graph id: ``aria.signal.v1``.
Task type: ``com.etzhayyim.agent.aria``.

Six-signal parallel fetch → entropy computation → cross-signal mutual information
→ Von Neumann minimax action selection → reverse-topo ingestion replan → audit.

ADR-2604291800 (Well-Becoming objective), ADR-2604251830 (Shannon η).
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from kotodama.kotoba_datomic import get_kotoba_client

log = logging.getLogger(__name__)

# Axis weights for A_info = Σ w_k × η_k  (sum = 4.475, normalises to η_global)
AXIS_WEIGHTS: dict[str, float] = {
    "emotion":   1.0,
    "attention": 0.875,
    "request":   0.875,
    "market":    0.575,
    "money":     0.575,
    "influence": 0.575,
}
_AREA_NORM = 4.475  # sum of weights above


# ─── State ──────────────────────────────────────────────────────────────


class AriaState(TypedDict, total=False):
    # Inputs
    context: dict[str, Any]
    threadId: str
    budgetMs: int

    # 6 signal slots (filled by _ingest_all)
    emotion:   dict[str, Any]   # {eta, magnitude, valence, entropy_h, source}
    attention: dict[str, Any]
    request:   dict[str, Any]
    market:    dict[str, Any]
    money:     dict[str, Any]
    influence: dict[str, Any]

    # Computed
    area_integral:     float        # A_info = Σ w_k × η_k
    eta_global:        float        # area_integral / 4.475
    mutual_info_top3:  list[dict]   # top MI pairs {sig_a, sig_b, mi_bits}
    minimax_result:    dict         # {selected_action, regret, worst_u, best_u}
    next_ingest_order: list[str]    # reverse-topo priority order

    # Audit
    audit_rkey: str
    error: str


# ─── Nodes ──────────────────────────────────────────────────────────────


def _safe_signal(result: Any, name: str) -> dict[str, Any]:
    """Normalise a primitive return value into a signal dict."""
    if isinstance(result, dict):
        return result
    return {"eta": 0.0, "source": name, "raw": str(result)[:200]}


def _ingest_all(state: AriaState) -> AriaState:
    """Call all 6 aria_signal primitives sequentially and merge into state."""
    # Lazy import to avoid circular deps at module load time.
    from kotodama.primitives import aria_signal  # noqa: PLC0415

    ctx = state.get("context") or {}
    signals: dict[str, dict[str, Any]] = {}
    errors: list[str] = []

    tasks = [
        ("emotion",   aria_signal.task_aria_emotion_ingest),
        ("attention", aria_signal.task_aria_attention_ingest),
        ("request",   aria_signal.task_aria_request_ingest),
        ("market",    aria_signal.task_aria_market_delta_ingest),
        ("money",     aria_signal.task_aria_money_flow_ingest),
        ("influence", aria_signal.task_aria_influence_ingest),
    ]
    for name, fn in tasks:
        try:
            signals[name] = _safe_signal(fn(context=ctx), name)
        except Exception as exc:  # noqa: BLE001
            log.warning("aria ingest %s failed: %s", name, exc)
            signals[name] = {"eta": 0.0, "source": name, "error": str(exc)[:120]}
            errors.append(f"{name}:{type(exc).__name__}")

    updates: AriaState = {
        **state,
        "emotion":   signals["emotion"],
        "attention": signals["attention"],
        "request":   signals["request"],
        "market":    signals["market"],
        "money":     signals["money"],
        "influence": signals["influence"],
    }
    if errors:
        updates["error"] = ";".join(errors)
    return updates


def _compute_area(state: AriaState) -> AriaState:
    """Compute A_info, eta_global, and top-3 pairwise MI estimates."""
    etas: dict[str, float] = {}
    for sig in AXIS_WEIGHTS:
        slot = state.get(sig) or {}
        try:
            etas[sig] = float(slot.get("eta") or 0.0)
        except (TypeError, ValueError):
            etas[sig] = 0.0

    area = sum(AXIS_WEIGHTS[k] * etas[k] for k in AXIS_WEIGHTS)
    eta_global = area / _AREA_NORM

    # Pairwise MI proxy: |Δη_a × Δη_b| (cheap, no joint distribution needed)
    keys = list(AXIS_WEIGHTS.keys())
    pairs: list[dict] = []
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = keys[i], keys[j]
            mi = abs((etas[a] - 0.5) * (etas[b] - 0.5))
            pairs.append({"sig_a": a, "sig_b": b, "mi_bits": round(mi, 6)})
    pairs.sort(key=lambda p: p["mi_bits"], reverse=True)

    return {
        **state,
        "area_integral":    round(area, 6),
        "eta_global":       round(eta_global, 6),
        "mutual_info_top3": pairs[:3],
    }


def _minimax_select(state: AriaState) -> AriaState:
    """Call aria_signal.task_aria_minimax_sweep() and store result."""
    from kotodama.primitives import aria_signal  # noqa: PLC0415

    try:
        result = aria_signal.task_aria_minimax_sweep(
            eta_global=state.get("eta_global") or 0.0,
            area_integral=state.get("area_integral") or 0.0,
            signals={
                k: state.get(k) or {}  # type: ignore[literal-required]
                for k in AXIS_WEIGHTS
            },
        )
        minimax = result if isinstance(result, dict) else {"raw": str(result)[:200]}
    except Exception as exc:  # noqa: BLE001
        log.warning("aria minimax_sweep failed: %s", exc)
        minimax = {"error": str(exc)[:120], "selected_action": "noop"}

    return {**state, "minimax_result": minimax}


def _reverse_topo(state: AriaState) -> AriaState:
    """Call aria_signal.task_aria_reverse_topo_replan() for next ingest order."""
    from kotodama.primitives import aria_signal  # noqa: PLC0415

    try:
        result = aria_signal.task_aria_reverse_topo_replan(
            mutual_info_top3=state.get("mutual_info_top3") or [],
            minimax_result=state.get("minimax_result") or {},
        )
        order = result if isinstance(result, list) else list(AXIS_WEIGHTS.keys())
    except Exception as exc:  # noqa: BLE001
        log.warning("aria reverse_topo failed: %s", exc)
        order = list(AXIS_WEIGHTS.keys())

    return {**state, "next_ingest_order": order}


def _audit(state: AriaState) -> AriaState:
    """Insert one row into vertex_wellbecoming_event for OCEL trail in kotoba Datom log."""
    ts_ms = int(time.time() * 1000)
    rkey = f"aria-{ts_ms}"
    vertex_id = f"did:web:langgraph.etzhayyim.com:com.etzhayyim.signal.aria:{rkey}:create"
    # Use datetime.now(timezone.utc) for created_at
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "area_integral": state.get("area_integral"),
        "eta_global":    state.get("eta_global"),
        "minimax":       state.get("minimax_result"),
        "threadId":      state.get("threadId"),
    }
    # Construct the row dictionary for insert_row
    row_dict = {
        "vertex_id": vertex_id,
        "event_type": "aria.signal.ingest",
        "actor_did": "did:web:langgraph.etzhayyim.com",
        "payload_json": json.dumps(payload, ensure_ascii=False),
        "ts_ms": ts_ms,
        "created_at": created_at,
    }
    try:
        get_kotoba_client().insert_row("vertex_wellbecoming_event", row_dict)
        return {**state, "audit_rkey": rkey}
    except Exception as exc:  # noqa: BLE001
        log.warning("aria audit emit failed: %s", exc)
        return {**state, "audit_rkey": ""}


# ─── Graph ──────────────────────────────────────────────────────────────


def build_graph() -> Any:
    g = StateGraph(AriaState)
    g.add_node("ingest_all",      _ingest_all)
    g.add_node("compute_area",    _compute_area)
    g.add_node("minimax_select",  _minimax_select)
    g.add_node("reverse_topo",    _reverse_topo)
    g.add_node("audit",           _audit)

    g.add_edge(START,            "ingest_all")
    g.add_edge("ingest_all",     "compute_area")
    g.add_edge("compute_area",   "minimax_select")
    g.add_edge("minimax_select", "reverse_topo")
    g.add_edge("reverse_topo",   "audit")
    g.add_edge("audit",          END)

    try:
        from langgraph.checkpoint.memory import MemorySaver  # noqa: PLC0415
        return g.compile(checkpointer=MemorySaver())
    except Exception:  # noqa: BLE001
        return g.compile()


aria_graph = build_graph()


# ─── Zeebe task entrypoint ───────────────────────────────────────────────


async def task_aria_agent(
    context: dict | None = None,
    threadId: str = "",
    budgetMs: int = 60_000,
) -> dict[str, Any]:
    """Entry point for Zeebe task type ``com.etzhayyim.agent.aria``.

    The BPMN caller passes ``context`` (FEEL context → dict), optional
    ``threadId`` (instance key), and ``budgetMs`` (soft wall-clock cap).
    Returns a flat dict of AriaState keys suitable for BPMN output mapping.
    """
    initial: AriaState = {
        "context":  context or {},
        "threadId": threadId or str(uuid.uuid4()),
        "budgetMs": int(budgetMs) if budgetMs else 60_000,
    }
    try:
        final = await aria_graph.ainvoke(
            initial,
            config={"configurable": {"thread_id": initial["threadId"]}},
        )
    except Exception as exc:  # noqa: BLE001
        log.error("aria_graph.ainvoke failed: %s", exc)
        return {"error": f"{type(exc).__name__}:{str(exc)[:200]}", "audit_rkey": ""}

    return {
        "area_integral":     final.get("area_integral") or 0.0,
        "eta_global":        final.get("eta_global") or 0.0,
        "mutual_info_top3":  final.get("mutual_info_top3") or [],
        "minimax_result":    final.get("minimax_result") or {},
        "next_ingest_order": final.get("next_ingest_order") or [],
        "audit_rkey":        final.get("audit_rkey") or "",
        "error":             final.get("error") or "",
    }
