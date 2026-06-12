"""
Zeebe worker for webmk (Web Marketing Proposal Agent) — ADR-2605072000.

Uses LangGraph for the intra-job agent loop (research → competitors → strategy →
copy → quality_gate → store). LangServer handles durable orchestration; LangGraph
handles intra-run state transitions.

Subscribes to 3 Zeebe job types:
  webmk.run_proposal_agent  — full LangGraph loop (main agent, ~60-120s)
  webmk.deliver_via_resend  — Resend transactional email
  webmk.create_ad_campaign  — XRPC call to ads.etzhayyim.com createCampaign

Run:
  python -m kotodama.webmk_worker_main

Env:
  AGENTGATEWAY_MCP_URL       — LangServer AgentGateway URL (default 127.0.0.1:8080)
  RW_URL              — RisingWave postgres URL
  ANTHROPIC_API_KEY   — Claude API key
  RESEND_API_KEY      — Resend API key
  RESEND_FROM         — sender address (default webmk@etzhayyim.com)
  ADS_XRPC_URL        — ads.etzhayyim.com base (default https://adsm4d5c.etzhayyim.com)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Annotated, Any, TypedDict

import httpx
from langchain_anthropic import ChatAnthropic
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from kotodama.langserver_compat import LangServerWorker, create_langserver_channel

from kotodama.kotoba_datomic import get_kotoba_client
from kotodama.local_agent_env import load_env_file, load_keychain_secret
from kotodama.llm import resolve_model_id

LOG = logging.getLogger("webmk_worker")

WEBMK_DID = "did:web:webmk.etzhayyim.com"
ADS_DID = "did:web:ads.etzhayyim.com"

QUALITY_THRESHOLD = float(os.environ.get("WEBMK_QUALITY_THRESHOLD", "0.7"))
RESEND_FROM = os.environ.get("RESEND_FROM", "webmk@etzhayyim.com")
ADS_XRPC_URL = os.environ.get("ADS_XRPC_URL", "https://adsm4d5c.etzhayyim.com")


# ─── helpers ──────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid(prefix: str) -> str:
    digest = hashlib.sha256(f"{prefix}{time.time_ns()}".encode()).hexdigest()[:12]
    return f"{prefix}-{digest}"


# ─── LangGraph state ──────────────────────────────────────────────────────


class ProposalState(TypedDict):
    proposal_id: str
    client_name: str
    website_url: str
    industry: str
    target_audience: str
    budget_jpy: int
    delivery_email: str
    create_ad_campaign: bool
    # populated by nodes
    company_context: str
    competitor_summary: str
    strategy_json: str
    copy_markdown: str
    quality_score: float
    retry_count: int
    messages: Annotated[list, add_messages]


# ─── LangGraph nodes ──────────────────────────────────────────────────────


async def node_research_company(state: ProposalState) -> dict[str, Any]:
    """Scrape company website and extract key facts using Claude."""
    llm = ChatAnthropic(model=resolve_model_id("default"))

    prompt = f"""You are a marketing researcher. Analyze this company:
URL: {state['website_url']}
Industry: {state['industry']}

Based on the URL and industry, infer and summarize:
1. Core product/service offering (2-3 sentences)
2. Apparent target customer segment
3. Current marketing tone (professional/casual/technical)
4. 3 potential marketing angles

Return a concise JSON object with keys: offering, targetSegment, marketingTone, angles[].
"""
    response = await llm.ainvoke(prompt)
    return {"company_context": str(response.content)}


async def node_analyze_competitors(state: ProposalState) -> dict[str, Any]:
    """Identify competitors and summarize their marketing approach."""
    llm = ChatAnthropic(model=resolve_model_id("default"))

    prompt = f"""You are a competitive intelligence analyst.

Company: {state['client_name']}
Industry: {state['industry']}
Company context: {state['company_context'][:800]}

Identify 3 likely competitors in this industry and summarize:
1. Their apparent marketing positioning
2. Keywords/themes they likely target
3. One gap or opportunity this company could exploit

Return JSON: competitors[{{name, positioning, keywords[], opportunity}}], mainGap
"""
    response = await llm.ainvoke(prompt)
    return {"competitor_summary": str(response.content)}


async def node_generate_strategy(state: ProposalState) -> dict[str, Any]:
    """Generate a full marketing strategy document."""
    llm = ChatAnthropic(model=resolve_model_id("default"))

    budget_str = f"¥{state['budget_jpy']:,}/month" if state["budget_jpy"] > 0 else "budget TBD"
    prompt = f"""You are a senior digital marketing strategist. Create a web marketing strategy.

Client: {state['client_name']}
Website: {state['website_url']}
Industry: {state['industry']}
Target audience: {state['target_audience'] or 'not specified'}
Budget: {budget_str}

Research:
{state['company_context'][:600]}

Competitive landscape:
{state['competitor_summary'][:600]}

Generate a structured marketing strategy JSON with:
{{
  "executiveSummary": "...",
  "channels": [{{"name": "SEO|SEM|SNS|content|email", "priority": 1-5, "rationale": "...", "kpis": []}}],
  "contentThemes": [],
  "sixMonthMilestones": [{{"month": 1-6, "goal": "...", "metric": "..."}}],
  "estimatedRoi": "..."
}}
"""
    response = await llm.ainvoke(prompt)
    return {"strategy_json": str(response.content)}


async def node_generate_copy(state: ProposalState) -> dict[str, Any]:
    """Generate ad copy and content examples in Markdown."""
    llm = ChatAnthropic(model=resolve_model_id("default"))

    prompt = f"""You are a copywriter. Write marketing copy for:

Client: {state['client_name']} ({state['website_url']})
Strategy summary: {state['strategy_json'][:400]}

Generate in Markdown:
## Hero Headline Options (3 variations)
## Sub-headline
## SNS Post Templates (Instagram, X/Twitter, LinkedIn — 1 each)
## Email Subject Line (A/B test pair)
## Google Ads Headlines (3 options, ≤30 chars each)
## Call to Action Options (3)
"""
    response = await llm.ainvoke(prompt)
    return {"copy_markdown": str(response.content)}


async def node_quality_gate(state: ProposalState) -> dict[str, Any]:
    """Score proposal quality. Retry once if below threshold."""
    llm = ChatAnthropic(model=resolve_model_id("default"))

    prompt = f"""Rate this marketing proposal on a scale 0.0–1.0.

Strategy JSON length: {len(state['strategy_json'])} chars
Copy Markdown length: {len(state['copy_markdown'])} chars
Strategy sample: {state['strategy_json'][:300]}
Copy sample: {state['copy_markdown'][:300]}

Score criteria: specificity (0.3), actionability (0.3), creativity (0.2), completeness (0.2).
Return ONLY a JSON: {{"score": 0.85, "reasoning": "..."}}
"""
    response = await llm.ainvoke(prompt)
    try:
        raw = str(response.content)
        start = raw.find("{")
        end = raw.rfind("}") + 1
        parsed = json.loads(raw[start:end])
        score = float(parsed.get("score", 0.5))
    except Exception:
        score = 0.5

    return {"quality_score": score}


async def node_store_proposal(state: ProposalState) -> dict[str, Any]:
    """Persist proposal to kotoba Datom log vertex_webmk_proposal."""
    def _run() -> None:
        client = get_kotoba_client()
        row_data = {
            "vertex_id": f"at://{WEBMK_DID}/com.etzhayyim.apps.webmk.proposal/{state['proposal_id']}",
            "record_id": state["proposal_id"],
            "owner_did": WEBMK_DID,
            "label": "proposal",
            "status": "generated",
            "proposal_id": state["proposal_id"],
            "strategy_json": state["strategy_json"][:8000],
            "copy_markdown": state["copy_markdown"][:8000],
            "quality_score": state["quality_score"],
            "lg_run_id": state["proposal_id"],
            "created_at": _now(),
            "updated_at": _now(),
            "sensitivity_ord": 2,
        }
        client.insert_row("vertex_webmk_proposal", row_data)
    await asyncio.get_event_loop().run_in_executor(None, _run)
    return {}


def should_retry(state: ProposalState) -> str:
    """Route after quality_gate: retry once if score too low."""
    if state["quality_score"] >= QUALITY_THRESHOLD:
        return "store"
    if state.get("retry_count", 0) >= 1:
        LOG.warning("quality gate failed after retry (score=%.2f), storing anyway", state["quality_score"])
        return "store"
    return "retry"


# ─── Build LangGraph ──────────────────────────────────────────────────────


def build_proposal_graph():
    g = StateGraph(ProposalState)

    g.add_node("research_company", node_research_company)
    g.add_node("analyze_competitors", node_analyze_competitors)
    g.add_node("generate_strategy", node_generate_strategy)
    g.add_node("generate_copy", node_generate_copy)
    g.add_node("quality_gate", node_quality_gate)
    g.add_node("store_proposal", node_store_proposal)

    g.add_edge(START, "research_company")
    g.add_edge("research_company", "analyze_competitors")
    g.add_edge("analyze_competitors", "generate_strategy")
    g.add_edge("generate_strategy", "generate_copy")
    g.add_edge("generate_copy", "quality_gate")
    g.add_conditional_edges(
        "quality_gate",
        should_retry,
        {
            "store": "store_proposal",
            "retry": "generate_strategy",
        },
    )
    g.add_edge("store_proposal", END)

    return g.compile(checkpointer=None)


PROPOSAL_GRAPH = build_proposal_graph()


# ─── webmk.run_proposal_agent ─────────────────────────────────────────────


async def task_run_proposal_agent(
    proposalId: str,
    clientName: str,
    websiteUrl: str,
    industry: str,
    targetAudience: str = "",
    budgetJpy: int = 0,
    deliveryEmail: str = "",
    createAdCampaign: bool = False,
    **_: Any,
) -> dict[str, Any]:
    """LangGraph agent loop: research → competitors → strategy → copy → quality → store."""
    LOG.info("run_proposal_agent start proposalId=%s client=%s", proposalId, clientName)

    initial_state: ProposalState = {
        "proposal_id": proposalId,
        "client_name": clientName,
        "website_url": websiteUrl,
        "industry": industry,
        "target_audience": targetAudience,
        "budget_jpy": budgetJpy,
        "delivery_email": deliveryEmail,
        "create_ad_campaign": createAdCampaign,
        "company_context": "",
        "competitor_summary": "",
        "strategy_json": "",
        "copy_markdown": "",
        "quality_score": 0.0,
        "retry_count": 0,
        "messages": [],
    }

    final_state = await PROPOSAL_GRAPH.ainvoke(initial_state)

    LOG.info(
        "run_proposal_agent done proposalId=%s score=%.2f",
        proposalId,
        final_state.get("quality_score", 0),
    )
    return {
        "proposalId": proposalId,
        "qualityScore": final_state.get("quality_score", 0.0),
        "strategyJsonLen": len(final_state.get("strategy_json", "")),
        "copyMarkdownLen": len(final_state.get("copy_markdown", "")),
    }


# ─── webmk.deliver_via_resend ─────────────────────────────────────────────


async def task_deliver_via_resend(
    proposalId: str,
    deliveryEmail: str = "",
    **_: Any,
) -> dict[str, Any]:
    """Fetch proposal from kotoba Datom log and deliver via Resend."""
    if not deliveryEmail:
        LOG.info("deliver_via_resend: no deliveryEmail, skipping proposalId=%s", proposalId)
        return {"status": "skipped", "reason": "no deliveryEmail"}

    def _fetch() -> dict[str, Any] | None:
        client = get_kotoba_client()
        return client.select_first_where(
            "vertex_webmk_proposal",
            "proposal_id",
            proposalId,
            columns=["client_name", "website_url", "strategy_json", "copy_markdown", "quality_score", "vertex_id"]
        )

    row = await asyncio.get_event_loop().run_in_executor(None, _fetch)
    if not row:
        raise ValueError(f"proposal not found: {proposalId}")

    client_name = row["client_name"] or "Your Company"
    strategy_json = row["strategy_json"] or ""
    copy_markdown = row["copy_markdown"] or ""
    quality_score = float(row["quality_score"] or 0)
    vertex_id = row["vertex_id"]

    html_body = f"""
<h1>Web Marketing Proposal — {client_name}</h1>
<p><strong>Quality Score:</strong> {quality_score:.0%}</p>

<h2>Strategy</h2>
<pre style="background:#f4f4f4;padding:16px;border-radius:8px;overflow:auto">{strategy_json[:3000]}</pre>

<h2>Ad Copy</h2>
<div style="background:#f9f9f9;padding:16px;border-radius:8px">
{copy_markdown[:3000].replace(chr(10), '<br>')}
</div>

<hr>
<p style="color:#888;font-size:12px">Generated by etzhayyim Web Marketing Agent · <a href="https://webmk.etzhayyim.com">webmk.etzhayyim.com</a></p>
"""

    resend_key = os.environ.get("RESEND_API_KEY", "")
    if not resend_key:
        LOG.warning("RESEND_API_KEY not set, skipping email delivery")
        return {"status": "skipped", "reason": "no RESEND_API_KEY"}

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
            json={
                "from": RESEND_FROM,
                "to": [deliveryEmail],
                "subject": f"Web Marketing Proposal — {client_name}",
                "html": html_body,
            },
            timeout=30,
        )
        resp.raise_for_status()
        email_id = resp.json().get("id", "")

    delivered_at = _now()

    def _mark_delivered() -> None:
        client = get_kotoba_client()
        row_data = {
            "vertex_id": vertex_id,
            "status": "delivered",
            "delivered_at": delivered_at,
            "updated_at": delivered_at,
        }
        client.insert_row("vertex_webmk_proposal", row_data)

    await asyncio.get_event_loop().run_in_executor(None, _mark_delivered)
    LOG.info("deliver_via_resend done proposalId=%s emailId=%s", proposalId, email_id)
    return {"status": "delivered", "emailId": email_id, "deliveredAt": delivered_at}


# ─── webmk.create_ad_campaign ─────────────────────────────────────────────


async def task_create_ad_campaign(
    proposalId: str,
    clientName: str,
    budgetJpy: int = 0,
    **_: Any,
) -> dict[str, Any]:
    """Call ads.etzhayyim.com createCampaign and link to kotoba Datom log."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{ADS_XRPC_URL}/xrpc/com.etzhayyim.apps.ads.createCampaign",
            json={
                "name": f"webmk-{proposalId[:8]} {clientName}",
                "description": f"Auto-generated campaign from webmk proposal {proposalId}",
                "advertiser": clientName,
                "budgetJpy": budgetJpy,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

    campaign_id = data.get("campaignId", "")
    campaign_did = data.get("did", "")
    edge_id = _uid("ecl")

    def _link() -> None:
        client = get_kotoba_client()
        row_data = {
            "edge_id": edge_id,
            "src_vid": f"at://{WEBMK_DID}/com.etzhayyim.apps.webmk.proposal/{proposalId}",
            "dst_vid": f"at://{ADS_DID}/com.etzhayyim.apps.ads.campaign/{campaign_id}",
            "relation_kind": "has_campaign",
            "proposal_id": proposalId,
            "ads_campaign_id": campaign_id,
            "ads_campaign_did": campaign_did,
            "created_at": _now(),
            "updated_at": _now(),
            "owner_did": WEBMK_DID,
            "sensitivity_ord": 2,
        }
        client.insert_row("edge_webmk_campaign_link", row_data)

    await asyncio.get_event_loop().run_in_executor(None, _link)
    LOG.info("create_ad_campaign done proposalId=%s campaignId=%s", proposalId, campaign_id)
    return {"campaignId": campaign_id, "campaignDid": campaign_did}


# ─── main ─────────────────────────────────────────────────────────────────


async def main() -> None:
    load_env_file()
    anthropic_key = load_keychain_secret("ANTHROPIC_API_KEY", "etzhayyim.anthropic", "ANTHROPIC_API_KEY")
    if anthropic_key:
        os.environ["ANTHROPIC_API_KEY"] = anthropic_key

    resend_key = load_keychain_secret("RESEND_API_KEY", "etzhayyim.resend", "RESEND_API_KEY")
    if resend_key:
        os.environ["RESEND_API_KEY"] = resend_key

    gateway = os.environ.get("AGENTGATEWAY_MCP_URL", "127.0.0.1:8080")
    channel = create_langserver_channel(grpc_address=gateway)
    worker = LangServerWorker(channel)

    worker.task(task_type="webmk.run_proposal_agent", timeout_ms=180_000)(task_run_proposal_agent)
    worker.task(task_type="webmk.deliver_via_resend", timeout_ms=60_000)(task_deliver_via_resend)
    worker.task(task_type="webmk.create_ad_campaign", timeout_ms=30_000)(task_create_ad_campaign)

    LOG.info("webmk worker started (gateway=%s)", gateway)

    stop_event = asyncio.Event()

    import signal as _signal

    def _handle_sigterm(*_: Any) -> None:
        LOG.info("SIGTERM received, shutting down")
        stop_event.set()

    _signal.signal(_signal.SIGTERM, _handle_sigterm)
    _signal.signal(_signal.SIGINT, _handle_sigterm)

    await worker.work(stop_event=stop_event)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    asyncio.run(main())
