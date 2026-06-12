"""kafun.tick.v1 — executor actor (path-based DID).

Input:  {pending_proposals: [...], fund_balance_jpy: int}  (from CF Worker)
Output: {decision: {vertex_kafun_action row + dispatch_hint}}

Pure decision graph — no side effects. Dispatch hint tells the pod-side
LangServer handler where to perform the actual work.

ADR-2605080600 / 2605082000.
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from kotodama.langgraph_graphs._kafun_common import EXECUTOR_DID, now_iso, rkey, vertex_id


class TickState(TypedDict, total=False):
    pending_proposals: list[dict[str, Any]]
    fund_balance_jpy: int
    decision: dict[str, Any] | None
    error: str | None


_DISPATCH = {
    "research":    {"transport": "langgraph", "graph": "kafun.research.v1"},
    "policy":      {"transport": "social",    "lexicon": "app.bsky.feed.post"},
    "tech":        {"transport": "langgraph", "graph": "kafun.research.v1"},
    "fund_spend":  {"transport": "xrpc",      "method": "com.etzhayyim.apps.kafun.fund.spend"},
    "public_post": {"transport": "social",    "lexicon": "app.bsky.feed.post"},
}


def _select(state: TickState) -> dict:
    pending = state.get("pending_proposals") or []
    balance = int(state.get("fund_balance_jpy", 0) or 0)
    candidates = [
        p for p in pending
        if str(p.get("status", "draft")) == "draft"
        and int(p.get("estimated_cost_jpy", 0) or 0) <= balance
    ]
    candidates.sort(
        key=lambda p: (int(p.get("priority", 3)), -int(p.get("estimated_cost_jpy", 0))),
    )
    if not candidates:
        return {"decision": None, "error": None}
    chosen = candidates[0]
    now = now_iso()
    action_type = str(chosen.get("action_type", "research"))
    key = rkey(f"action:{chosen.get('vertex_id', '')}:{now}")
    return {
        "decision": {
            "vertex_id":        vertex_id(EXECUTOR_DID, "action", key),
            "actor_did":        EXECUTOR_DID,
            "from_proposal_id": chosen.get("vertex_id", ""),
            "action_type":      action_type,
            "cost_jpy":         int(chosen.get("estimated_cost_jpy", 0) or 0),
            "status":           "dispatched",
            "dispatch_hint":    _DISPATCH.get(action_type, {"transport": "noop"}),
            "created_at":       now,
        },
        "error": None,
    }


def build_graph():
    g = StateGraph(TickState)
    g.add_node("select", _select)
    g.set_entry_point("select")
    g.add_edge("select", END)
    return g.compile()
