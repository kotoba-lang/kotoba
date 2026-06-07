"""kafun.research.v1 — researcher actor (path-based DID).

Input:  {category, query}
Output: {findings: [{vertex_id, actor_did=RESEARCHER_DID, category, title,
                     summary, evidence, confidence, created_at}]}

ADR-2605080600 / 2605082000 (graph definition as data).
"""

from __future__ import annotations

import json
import re
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from kotodama.langgraph_graphs._kafun_common import (
    RESEARCHER_DID, llm, now_iso, rkey, vertex_id,
)


class ResearchState(TypedDict, total=False):
    category: str
    query: str
    raw_output: str
    findings: list[dict[str, Any]]
    error: str | None


async def _query(state: ResearchState) -> dict:
    prompt = (
        f"あなたは花粉撲滅Fund の研究担当エージェント (DID: {RESEARCHER_DID}) です。\n"
        f"カテゴリ: {state.get('category', '')}\n"
        f"問い: {state.get('query', '')}\n\n"
        "東京・日本のスギ・ヒノキ花粉撲滅という最終目的に資する具体的な発見を "
        "JSON 配列で 3-7 件返してください。各要素は次のキーを持ちます:\n"
        '  {"title":"...","summary":"...","evidence":"...","confidence":0.0-1.0}\n'
        "JSON のみを返してください。"
    )
    try:
        return {"raw_output": await llm(prompt, temperature=0.3, max_tokens=2048), "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"raw_output": "", "findings": [], "error": str(exc)}


def _parse(state: ResearchState) -> dict:
    raw = state.get("raw_output") or ""
    if not raw:
        return {"findings": []}
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    items: list[dict[str, Any]] = []
    if m:
        try:
            items = json.loads(m.group(0))
        except json.JSONDecodeError:
            items = []

    now = now_iso()
    cat = str(state.get("category", ""))
    q = str(state.get("query", ""))
    findings: list[dict[str, Any]] = []
    for i, it in enumerate(items[:7]):
        key = rkey(f"{cat}:{q}:{i}:{it.get('title','')}")
        findings.append({
            "vertex_id":  vertex_id(RESEARCHER_DID, "research", key),
            "actor_did":  RESEARCHER_DID,
            "category":   cat,
            "title":      str(it.get("title", ""))[:200],
            "summary":    str(it.get("summary", ""))[:2000],
            "evidence":   str(it.get("evidence", ""))[:2000],
            "confidence": float(it.get("confidence", 0.5)),
            "created_at": now,
        })
    return {"findings": findings}


def build_graph():
    g = StateGraph(ResearchState)
    g.add_node("query", _query)
    g.add_node("parse", _parse)
    g.set_entry_point("query")
    g.add_edge("query", "parse")
    g.add_edge("parse", END)
    return g.compile()
