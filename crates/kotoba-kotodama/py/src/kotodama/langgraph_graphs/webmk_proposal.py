"""
webmk.createProposal — LangGraph StateGraph (ADR-2605080600 Phase 4).

assistant_id: "webmk_create_proposal"

Graph: START → research_company → analyze_competitors → generate_strategy
              → generate_copy → quality_gate → [retry?] → store_proposal → END

Replaces LangServer task_run_proposal_agent in webmk_worker_main.py.
Activation via routing_target='langgraph' on the createProposal binding row.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any, TypedDict

from kotodama.kotoba_datomic import get_kotoba_client
from kotodama import llm

WEBMK_DID = "did:web:webmk.etzhayyim.com"
QUALITY_THRESHOLD = 0.7


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid(prefix: str) -> str:
    digest = hashlib.sha256(f"{prefix}{time.time_ns()}".encode()).hexdigest()[:12]
    return f"{prefix}-{digest}"


# ── State ──────────────────────────────────────────────────────────────────

class ProposalState(TypedDict, total=False):
    # inputs
    proposalId: str
    clientName: str
    websiteUrl: str
    industry: str
    targetAudience: str
    budgetJpy: int
    deliveryEmail: str
    createAdCampaign: bool
    # internal
    company_context: str
    competitor_summary: str
    strategy_json: str
    copy_markdown: str
    quality_score: float
    retry_count: int
    # outputs
    ok: bool
    error: str | None


# ── Nodes ──────────────────────────────────────────────────────────────────

def research_company(state: ProposalState) -> dict[str, Any]:
    url = state.get("websiteUrl") or ""
    industry = state.get("industry") or ""
    system = "You are a marketing researcher. Respond with concise JSON only."
    user = (
        f"Analyze this company URL: {url}\nIndustry: {industry}\n\n"
        "Return JSON with keys: offering, targetSegment, marketingTone, angles[]"
    )
    try:
        resp = llm.call_tier("fast", system, user, max_tokens=600, temperature=0.3)
        return {"company_context": resp.get("content") or ""}
    except llm.LlmError as e:
        return {"company_context": f"(research failed: {e})"}


def analyze_competitors(state: ProposalState) -> dict[str, Any]:
    system = "You are a competitive intelligence analyst. Respond with concise JSON only."
    user = (
        f"Client: {state.get('clientName')}\nIndustry: {state.get('industry')}\n"
        f"Context: {(state.get('company_context') or '')[:600]}\n\n"
        "Identify 3 likely competitors. Return JSON: competitors[{name,positioning,keywords[],opportunity}], mainGap"
    )
    try:
        resp = llm.call_tier("fast", system, user, max_tokens=700, temperature=0.3)
        return {"competitor_summary": resp.get("content") or ""}
    except llm.LlmError as e:
        return {"competitor_summary": f"(analysis failed: {e})"}


def generate_strategy(state: ProposalState) -> dict[str, Any]:
    budget_jpy = int(state.get("budgetJpy") or 0)
    budget_str = f"¥{budget_jpy:,}/month" if budget_jpy > 0 else "budget TBD"
    system = "You are a senior digital marketing strategist. Respond with JSON only."
    user = (
        f"Client: {state.get('clientName')}\nWebsite: {state.get('websiteUrl')}\n"
        f"Industry: {state.get('industry')}\nBudget: {budget_str}\n\n"
        f"Research:\n{(state.get('company_context') or '')[:500]}\n\n"
        f"Competitors:\n{(state.get('competitor_summary') or '')[:500]}\n\n"
        "Return JSON: {executiveSummary, channels[{name,priority,rationale,kpis[]}], "
        "contentThemes[], sixMonthMilestones[{month,goal,metric}], estimatedRoi}"
    )
    try:
        resp = llm.call_tier("balanced", system, user, max_tokens=1200, temperature=0.4)
        return {"strategy_json": resp.get("content") or "", "retry_count": state.get("retry_count", 0)}
    except llm.LlmError as e:
        return {"strategy_json": f"(strategy failed: {e})", "retry_count": state.get("retry_count", 0)}


def generate_copy(state: ProposalState) -> dict[str, Any]:
    system = "You are a copywriter. Format output in Markdown."
    user = (
        f"Client: {state.get('clientName')} ({state.get('websiteUrl')})\n"
        f"Strategy: {(state.get('strategy_json') or '')[:400]}\n\n"
        "Write:\n## Hero Headlines (3)\n## Sub-headline\n## SNS Posts (Instagram/X/LinkedIn)\n"
        "## Email Subject Lines (A/B)\n## Google Ads Headlines (3, ≤30 chars)\n## CTA Options (3)"
    )
    try:
        resp = llm.call_tier("balanced", system, user, max_tokens=1000, temperature=0.5)
        return {"copy_markdown": resp.get("content") or ""}
    except llm.LlmError as e:
        return {"copy_markdown": f"(copy failed: {e})"}


def _envelope_content(state: ProposalState, envelope_key: str, legacy_key: str) -> str:
    """Phase E2: extract content from {envelope_key}.result.content (when the
    upstream node is mcp_tool com.etzhayyim.tools.llm.chat) and fall back to
    state.<legacy_key> if the envelope is absent (v1 path / direct unit
    test seeding). Returns '' if neither is set."""
    envelope = state.get(envelope_key)
    if isinstance(envelope, dict):
        result = envelope.get("result")
        if isinstance(result, dict):
            content = result.get("content")
            if isinstance(content, str) and content:
                return content
    legacy = state.get(legacy_key)
    return legacy if isinstance(legacy, str) else ""


def quality_gate(state: ProposalState) -> dict[str, Any]:
    system = "Rate marketing proposals. Return only JSON: {score: 0.0-1.0, reasoning: string}"
    strategy = _envelope_content(state, "strategyOut", "strategy_json")
    copy = _envelope_content(state, "copyOut", "copy_markdown")
    user = (
        f"Strategy ({len(strategy)} chars): {strategy[:300]}\n"
        f"Copy ({len(copy)} chars): {copy[:300]}\n\n"
        "Score on specificity(0.3), actionability(0.3), creativity(0.2), completeness(0.2)."
    )
    try:
        resp = llm.call_tier("fast", system, user, max_tokens=200, temperature=0.1)
        raw = resp.get("content") or ""
        start = raw.find("{")
        end = raw.rfind("}") + 1
        parsed = json.loads(raw[start:end]) if start >= 0 and end > start else {}
        score = float(parsed.get("score", 0.5))
    except Exception:
        score = 0.5
    # Phase D2 (ADR-2605082000): embed routing decision so the topology uses
    # field-based conditional edges, retiring should_retry. Mirrors the
    # router: store if score≥threshold OR retry_count≥1, else retry.
    retry_count = int(state.get("retry_count") or 0)
    next_route = "store" if (score >= QUALITY_THRESHOLD or retry_count >= 1) else "retry"
    return {"quality_score": score, "nextRoute": next_route}


def should_retry(state: ProposalState) -> str:
    if (state.get("quality_score") or 0.0) >= QUALITY_THRESHOLD:
        return "store"
    if (state.get("retry_count") or 0) >= 1:
        return "store"
    return "retry"


def store_proposal(state: ProposalState) -> dict[str, Any]:
    proposal_id = state.get("proposalId") or _uid("wp")
    # Phase E2: read content from the mcp_tool envelope when v2 ran the
    # upstream LLM nodes; fall back to legacy state fields otherwise.
    strategy = _envelope_content(state, "strategyOut", "strategy_json")[:8000]
    copy = _envelope_content(state, "copyOut", "copy_markdown")[:8000]
    try:
        get_kotoba_client().insert_row("vertex_webmk_proposal", {
            "vertex_id": f'at://{WEBMK_DID}/com.etzhayyim.apps.webmk.proposal/{proposal_id}',
            "record_id": proposal_id,
            "owner_did": WEBMK_DID,
            "label": 'proposal',
            "status": 'generated',
            "proposal_id": proposal_id,
            "strategy_json": strategy,
            "copy_markdown": copy,
            "quality_score": state.get('quality_score') or 0.0,
            "lg_run_id": proposal_id,
            "created_at": _now(),
            "updated_at": _now(),
            "sensitivity_ord": 2,
        })
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ── Graph factory ──────────────────────────────────────────────────────────

def build_graph():
    from langgraph.graph import END, StateGraph

    g = StateGraph(ProposalState)
    g.add_node("research_company", research_company)
    g.add_node("analyze_competitors", analyze_competitors)
    g.add_node("generate_strategy", generate_strategy)
    g.add_node("generate_copy", generate_copy)
    g.add_node("quality_gate", quality_gate)
    g.add_node("store_proposal", store_proposal)

    g.set_entry_point("research_company")
    g.add_edge("research_company", "analyze_competitors")
    g.add_edge("analyze_competitors", "generate_strategy")
    g.add_edge("generate_strategy", "generate_copy")
    g.add_edge("generate_copy", "quality_gate")
    g.add_conditional_edges(
        "quality_gate",
        should_retry,
        {"store": "store_proposal", "retry": "generate_strategy"},
    )
    g.add_edge("store_proposal", END)

    return g.compile()
