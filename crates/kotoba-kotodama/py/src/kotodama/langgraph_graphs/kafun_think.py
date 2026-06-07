"""kafun.think.v1 — proposer actor (path-based DID).

Input:  {seed_findings: [...]}   from prior kafun.research runs
Output: {insight: {...}, proposals: [...]}  (vertex_kafun_insight + vertex_kafun_proposal)

ADR-2605080600 / 2605082000.
"""

from __future__ import annotations

import json
import re
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from kotodama.langgraph_graphs._kafun_common import (
    PROPOSER_DID, llm, now_iso, rkey, vertex_id,
)


class ThinkState(TypedDict, total=False):
    seed_findings: list[dict[str, Any]]
    insight: dict[str, Any] | None
    proposals: list[dict[str, Any]]
    error: str | None


async def _synthesize(state: ThinkState) -> dict:
    seeds = state.get("seed_findings") or []
    bullet = "\n".join(
        f"- [{f.get('category')}] {f.get('title')}: {f.get('summary')}"
        for f in seeds[:20]
    )
    prompt = (
        f"あなたは花粉撲滅Fund の提案担当エージェント (DID: {PROPOSER_DID}) です。\n"
        "以下は研究担当が集めた findings です:\n"
        f"{bullet}\n\n"
        "次の JSON を返してください (それ以外の文字を出力しない):\n"
        "{\n"
        '  "insight": {"summary":"...","rationale":"..."},\n'
        '  "proposals": [\n'
        '    {"title":"...","action_type":"research|policy|tech|fund_spend|public_post",\n'
        '     "estimated_cost_jpy":0,"expected_impact":"...","priority":1-5}\n'
        "  ]\n"
        "}"
    )
    try:
        raw = await llm(prompt, temperature=0.4, max_tokens=2048)
    except Exception as exc:  # noqa: BLE001
        return {"insight": None, "proposals": [], "error": str(exc)}

    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return {"insight": None, "proposals": [], "error": "no_json"}
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError as exc:
        return {"insight": None, "proposals": [], "error": str(exc)}

    now = now_iso()
    seed_titles = ":".join(f.get("title", "") for f in seeds[:5])
    ins = data.get("insight") or {}
    ins_key = rkey(f"insight:{seed_titles}:{now}")
    insight = {
        "vertex_id":  vertex_id(PROPOSER_DID, "insight", ins_key),
        "actor_did":  PROPOSER_DID,
        "summary":    str(ins.get("summary", ""))[:2000],
        "rationale":  str(ins.get("rationale", ""))[:2000],
        "source_finding_ids": [f.get("vertex_id", "") for f in seeds[:20]],
        "created_at": now,
    }

    proposals: list[dict[str, Any]] = []
    for i, p in enumerate((data.get("proposals") or [])[:3]):
        key = rkey(f"proposal:{ins_key}:{i}:{p.get('title','')}")
        proposals.append({
            "vertex_id":          vertex_id(PROPOSER_DID, "proposal", key),
            "actor_did":          PROPOSER_DID,
            "from_insight_id":    insight["vertex_id"],
            "title":              str(p.get("title", ""))[:200],
            "action_type":        str(p.get("action_type", "research")),
            "estimated_cost_jpy": int(p.get("estimated_cost_jpy", 0) or 0),
            "expected_impact":    str(p.get("expected_impact", ""))[:1000],
            "priority":           int(p.get("priority", 3) or 3),
            "status":             "draft",
            "created_at":         now,
        })

    return {"insight": insight, "proposals": proposals, "error": None}


def build_graph():
    g = StateGraph(ThinkState)
    g.add_node("synthesize", _synthesize)
    g.set_entry_point("synthesize")
    g.add_edge("synthesize", END)
    return g.compile()
