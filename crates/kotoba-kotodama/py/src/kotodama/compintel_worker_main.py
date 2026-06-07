"""
Zeebe worker for compintel (Competitive Intelligence Dashboard) — ADR-2605072000.

LangGraph intra-job multi-dimension research loop:
  fetch_signals → analyze_pricing → analyze_product → analyze_hiring
  → score_threat → store_snapshot

LangServer job types:
  compintel.run_research_agent  — LangGraph loop per competitor (300s)
  compintel.score_threats       — Diff previous snapshot, emit alerts (60s)
  compintel.send_digest         — Resend weekly digest for high-severity alerts (60s)

Weekly schedule: Zeebe BPMN timer "0 23 * * 0" (Monday 08:00 JST).
No PII — all data is public competitive intelligence.

Run:
  python -m kotodama.compintel_worker_main

Env:
  AGENTGATEWAY_MCP_URL      — LangServer AgentGateway URL (default 127.0.0.1:8080)
  RW_URL             — RisingWave postgres URL
  ANTHROPIC_API_KEY
  RESEND_API_KEY
  RESEND_FROM        — sender (default digest@etzhayyim.com)
  DIGEST_TO          — recipient for weekly digest
  ADS_XRPC_URL       — ads.etzhayyim.com base (default https://adsm4d5c.etzhayyim.com)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import operator
import os
from datetime import datetime, timezone
from typing import Annotated, Any, TypedDict

import httpx
from langchain_anthropic import ChatAnthropic
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Send
from kotodama.langserver_compat import LangServerWorker, create_langserver_channel

from kotodama.kotoba_datomic import get_kotoba_client
from kotodama.local_agent_env import load_env_file
from kotodama.llm import resolve_model_id

LOG = logging.getLogger("compintel_worker")

COMPINTEL_DID = "did:web:compintel.etzhayyim.com"
ADS_XRPC_URL = os.environ.get("ADS_XRPC_URL", "https://adsm4d5c.etzhayyim.com")
RESEND_FROM = os.environ.get("RESEND_FROM", "digest@etzhayyim.com")
DIGEST_TO = os.environ.get("DIGEST_TO", "")


# ---------------------------------------------------------------------------
# LangGraph state
# ---------------------------------------------------------------------------

class CompintelState(TypedDict):
    messages: Annotated[list[Any], add_messages]
    competitor_id: str
    competitor_name: str
    website: str
    tracking_dimensions: list[str]
    # signals per dimension (written by parallel super-step)
    pricing_signals: str
    product_signals: str
    hiring_signals: str
    funding_signals: str
    press_signals: str
    # judge accumulator (Pregel Send map-reduce, von Neumann minimax)
    judges: Annotated[list[dict[str, Any]], operator.add]
    # scoring
    latest_summary: str
    threat_score: float
    stored: bool


# ---------------------------------------------------------------------------
# LangGraph nodes
# ---------------------------------------------------------------------------

def _llm() -> ChatAnthropic:
    model_id = resolve_model_id("general")
    return ChatAnthropic(model=model_id, temperature=0.2, max_tokens=1024)


def fetch_signals(state: CompintelState) -> dict[str, Any]:
    """Gather structured data about the competitor from the graph (news articles)."""

    competitor_name = state.get("competitor_name", "")

    # R0: Replaced SQL ILIKE with Python 'in' operator, and ORDER BY/LIMIT
    # with Python sorting/slicing due to kotoba client shim limitations.
    all_rows = get_kotoba_client().select_where(
        "vertex_news_article",
        "body_text",
        None, # fetch all for this column to apply ILIKE in python
        columns=["title", "body_text", "published_at"],
        limit=2000 # Increased limit for Python-side filtering
    )
    # Filter by body_text ILIKE %competitor_name% and sort
    rows = [
        r for r in all_rows
        if competitor_name.lower() in (r.get("body_text", "") or "").lower()
    ]
    rows.sort(key=lambda r: r.get("published_at", ""), reverse=True)
    rows = rows[:10]
    signal_text = "\n".join(
        f"- [{r.get('published_at', '')}] {r.get('title', '')}: {(r.get('body_text') or '')[:200]}"
        for r in rows
    ) if rows else "(no recent news found)"

    LOG.info("fetch_signals: competitor=%s articles=%d", competitor_name, len(rows) if rows else 0)
    return {"press_signals": signal_text}


def analyze_pricing(state: CompintelState) -> dict[str, Any]:
    """LLM extract pricing signals from available data."""
    if "pricing" not in state.get("tracking_dimensions", []):
        return {"pricing_signals": "not tracked"}
    llm = _llm()
    press = state.get("press_signals", "")
    name = state.get("competitor_name", "the competitor")
    prompt = (
        f"Extract any pricing signals for {name} from the following news snippets.\n"
        f"Snippets: {press[:1500]}\n\n"
        "Summarize pricing signals in 2-3 sentences. If none found, say 'No pricing signals detected.'"
    )
    resp = llm.invoke(prompt)
    return {"pricing_signals": str(resp.content).strip()}


def analyze_product(state: CompintelState) -> dict[str, Any]:
    """LLM extract product signals."""
    if "product" not in state.get("tracking_dimensions", []):
        return {"product_signals": "not tracked"}
    llm = _llm()
    press = state.get("press_signals", "")
    name = state.get("competitor_name", "the competitor")
    prompt = (
        f"Extract product launches, feature announcements, or R&D signals for {name}.\n"
        f"Snippets: {press[:1500]}\n\n"
        "Summarize product signals in 2-3 sentences."
    )
    resp = llm.invoke(prompt)
    return {"product_signals": str(resp.content).strip()}


def analyze_hiring(state: CompintelState) -> dict[str, Any]:
    """LLM extract hiring signals."""
    if "hiring" not in state.get("tracking_dimensions", []):
        return {"hiring_signals": "not tracked"}
    llm = _llm()
    press = state.get("press_signals", "")
    name = state.get("competitor_name", "the competitor")
    prompt = (
        f"Extract hiring signals (headcount growth, key hires, layoffs) for {name}.\n"
        f"Snippets: {press[:1500]}\n\n"
        "Summarize hiring signals in 1-2 sentences."
    )
    resp = llm.invoke(prompt)
    return {"hiring_signals": str(resp.content).strip()}


def collect_signals(state: CompintelState) -> dict[str, Any]:
    """Super-step barrier: waits for parallel analyze_* nodes to complete.

    Returns nothing — exists solely as a fan-in point before the Send dispatch
    so all three signal channels are populated when judges read the state.
    """
    return {}


_JUDGE_PERSONAS = ("conservative", "neutral", "aggressive")


def dispatch_judges(state: CompintelState) -> list[Send]:
    """Pregel Send: fan out one judge_node per persona (von Neumann minimax)."""
    return [
        Send("judge_node", {**state, "_judge_persona": persona})
        for persona in _JUDGE_PERSONAS
    ]


_JUDGE_PROMPT_SUFFIX = (
    'You are a competitive intelligence analyst.\n'
    'Respond with JSON only: {"threat_score": 0.0-1.0, "summary": "1-2 sentence assessment"}'
)


def judge_node(state: dict[str, Any]) -> dict[str, Any]:
    """Wrap reusable judge subgraph (ADR-2605080000 §6-Layer composition).

    Maps compintel state -> JudgeInput, invokes the compiled subgraph, then
    folds the output back into the parent `judges` accumulator channel.
    """
    from kotodama.langgraph_graphs._subgraphs.judge import run_judge

    persona = state.get("_judge_persona", "neutral")
    name = state.get("competitor_name", "the competitor")
    signals = {
        "pricing": state.get("pricing_signals", ""),
        "product": state.get("product_signals", ""),
        "hiring": state.get("hiring_signals", ""),
        "funding": state.get("funding_signals", ""),
        "press": state.get("press_signals", ""),
    }
    judge = run_judge(
        persona=persona,
        subject=f"competitive threat from {name}",
        signals=signals,
        prompt_suffix=_JUDGE_PROMPT_SUFFIX,
    )
    return {"judges": [judge]}


def reduce_judges(state: CompintelState) -> dict[str, Any]:
    """Median-aggregate judge scores; pick summary closest to consensus."""
    judges = state.get("judges", []) or []
    if not judges:
        return {"threat_score": 0.5, "latest_summary": ""}
    scores = sorted(float(j.get("score", 0.5)) for j in judges)
    median = scores[len(scores) // 2]
    closest = min(judges, key=lambda j: abs(float(j.get("score", 0.5)) - median))
    LOG.info(
        "reduce_judges: competitor=%s n=%d median=%.2f scores=%s",
        state.get("competitor_name"), len(judges), median,
        ",".join(f"{s:.2f}" for s in scores),
    )
    return {
        "threat_score": round(median, 3),
        "latest_summary": str(closest.get("summary", "")),
    }


def store_snapshot(state: CompintelState) -> dict[str, Any]:
    """INSERT competitive snapshot to vertex_compintel_snapshot (no onConflict — PK implicit)."""

    competitor_id = state["competitor_id"]
    now = datetime.now(timezone.utc).isoformat()

    summary_hash = hashlib.sha256(state.get("latest_summary", "").encode()).hexdigest()[:16]
    snapshot_id = hashlib.sha256(f"snapshot:{competitor_id}:{now}".encode()).hexdigest()
    vertex_id = snapshot_id

    snapshot_row = {
        "vertex_id": vertex_id,
        "record_id": f"compintel:snapshot:{competitor_id}:{now}",
        "owner_did": COMPINTEL_DID,
        "label": "CompintelSnapshot",
        "status": "active",
        "agent_did": COMPINTEL_DID,
        "created_at": now,
        "updated_at": now,
        "sensitivity_ord": 0,
        "snapshot_id": snapshot_id,
        "competitor_id": competitor_id,
        "latest_summary": state.get("latest_summary", ""),
        "pricing_signals": state.get("pricing_signals", ""),
        "product_signals": state.get("product_signals", ""),
        "hiring_signals": state.get("hiring_signals", ""),
        "funding_signals": state.get("funding_signals", ""),
        "press_signals": state.get("press_signals", ""),
        "threat_score": state.get("threat_score", 0.5),
        "content_hash": summary_hash,
    }
    get_kotoba_client().insert_row("vertex_compintel_snapshot", snapshot_row)

    # update competitor threat_score + last_refreshed_at
    comp_vid = hashlib.sha256(f"competitor:{competitor_id}".encode()).hexdigest()
    # R0: Fetching existing competitor row to perform an upsert for update
    existing_comp = get_kotoba_client().select_first_where(
        "vertex_compintel_competitor",
        "vertex_id",
        comp_vid
    )
    if existing_comp:
        existing_comp["threat_score"] = state.get("threat_score", 0.5)
        existing_comp["last_refreshed_at"] = now
        existing_comp["updated_at"] = now
        get_kotoba_client().insert_row("vertex_compintel_competitor", existing_comp)
    else:
        LOG.warning("store_snapshot: Competitor %s not found for update", competitor_id)

    LOG.info("store_snapshot: competitor_id=%s snapshot_id=%s score=%.2f", competitor_id, snapshot_id, state.get("threat_score", 0))
    return {"stored": True}


# ---------------------------------------------------------------------------
# Build LangGraph
# ---------------------------------------------------------------------------

def _build_graph() -> Any:
    """Pregel BSP graph.

    Layout (super-steps):
      1. fetch_signals
      2. analyze_pricing | analyze_product | analyze_hiring   (parallel, same step)
      3. collect_signals                                        (fan-in barrier)
      4. judge_node × N                                         (Send fan-out)
      5. reduce_judges                                          (median consensus)
      6. store_snapshot
    """
    g: StateGraph = StateGraph(CompintelState)
    g.add_node("fetch_signals", fetch_signals)
    g.add_node("analyze_pricing", analyze_pricing)
    g.add_node("analyze_product", analyze_product)
    g.add_node("analyze_hiring", analyze_hiring)
    g.add_node("collect_signals", collect_signals)
    g.add_node("judge_node", judge_node)
    g.add_node("reduce_judges", reduce_judges)
    g.add_node("store_snapshot", store_snapshot)

    g.add_edge(START, "fetch_signals")
    # parallel super-step: 3 analyze nodes fire concurrently
    g.add_edge("fetch_signals", "analyze_pricing")
    g.add_edge("fetch_signals", "analyze_product")
    g.add_edge("fetch_signals", "analyze_hiring")
    # fan-in barrier
    g.add_edge("analyze_pricing", "collect_signals")
    g.add_edge("analyze_product", "collect_signals")
    g.add_edge("analyze_hiring", "collect_signals")
    # Send map-reduce: collect_signals → judge_node × N → reduce_judges
    g.add_conditional_edges("collect_signals", dispatch_judges, ["judge_node"])
    g.add_edge("judge_node", "reduce_judges")
    g.add_edge("reduce_judges", "store_snapshot")
    g.add_edge("store_snapshot", END)
    return g.compile()


_GRAPH = _build_graph()


# ---------------------------------------------------------------------------
# LangServer handlers
# ---------------------------------------------------------------------------

def _make_worker() -> LangServerWorker:
    gateway = os.environ.get("AGENTGATEWAY_MCP_URL", "127.0.0.1:8080")
    channel = create_langserver_channel(grpc_address=gateway)
    return LangServerWorker(channel)


async def task_run_research_agent(
    competitor_id: str = "",
    mode: str = "single_deep",
    **_: Any,
) -> dict[str, Any]:
    """LangGraph research loop. mode=single_deep for trackCompetitor, mode=batch_all for weekly refresh."""


    if mode == "batch_all":
        competitors = get_kotoba_client().select_where(
            "vertex_compintel_competitor",
            "status",
            "active",
            columns=["competitor_id", "competitor_name", "website", "tracking_dimensions"]
        )
    else:
        row = get_kotoba_client().select_first_where(
            "vertex_compintel_competitor",
            "competitor_id",
            competitor_id,
            columns=["competitor_id", "competitor_name", "website", "tracking_dimensions"]
        )
        competitors = [row] if row else []

    results = []
    for comp in (competitors or []):
        comp_id = comp.get("competitor_id", "")
        dimensions_raw = comp.get("tracking_dimensions", "")
        dimensions: list[str] = []
        try:
            dimensions = json.loads(dimensions_raw) if dimensions_raw else ["pricing", "product", "hiring"]
        except Exception:
            dimensions = ["pricing", "product", "hiring"]

        init_state: CompintelState = {
            "messages": [],
            "competitor_id": comp_id,
            "competitor_name": comp.get("competitor_name", ""),
            "website": comp.get("website", ""),
            "tracking_dimensions": dimensions,
            "pricing_signals": "",
            "product_signals": "",
            "hiring_signals": "",
            "funding_signals": "",
            "press_signals": "",
            "latest_summary": "",
            "threat_score": 0.5,
            "stored": False,
        }
        final = await asyncio.to_thread(_GRAPH.invoke, init_state)
        results.append({"competitorId": comp_id, "threatScore": final.get("threat_score", 0)})

    return {"researchedCount": len(results), "results": results}


async def task_score_threats(
    **_: Any,
) -> dict[str, Any]:
    """Compare latest snapshots to previous — emit alerts for significant changes."""

    now = datetime.now(timezone.utc).isoformat()

    # find competitors with threat_score >= 0.7 (high)
    # R0: Replaced SQL WHERE threat_score >= 0.7 with Python filtering due to kotoba client shim limitations.
    all_competitors = get_kotoba_client().select_where(
        "vertex_compintel_competitor",
        "status",
        "active",
        columns=["competitor_id", "competitor_name", "threat_score"]
    )
    high_threat = [
        c for c in all_competitors
        if c.get("threat_score", 0.0) >= 0.7
    ]
    alert_count = 0
    for comp in (high_threat or []):
        alert_id = hashlib.sha256(f"alert:{comp.get('competitor_id','')}:{now}".encode()).hexdigest()
        vertex_id = alert_id
        alert_row = {
            "vertex_id": vertex_id,
            "record_id": f"compintel:alert:{alert_id}",
            "owner_did": COMPINTEL_DID,
            "label": "CompintelAlert",
            "status": "active",
            "agent_did": COMPINTEL_DID,
            "created_at": now,
            "updated_at": now,
            "sensitivity_ord": 0,
            "alert_id": alert_id,
            "competitor_id": comp.get("competitor_id", ""),
            "dimension": "overall",
            "summary": f"High threat score: {comp.get('threat_score', 0):.2f} for {comp.get('competitor_name', '')}",
            "severity": "high",
        }
        get_kotoba_client().insert_row("vertex_compintel_alert", alert_row)
        alert_count += 1

    has_high_severity = alert_count > 0
    LOG.info("task_score_threats: alerts=%d has_high=%s", alert_count, has_high_severity)
    return {"alertCount": alert_count, "hasHighSeverityAlerts": has_high_severity}


async def task_send_digest(
    **_: Any,
) -> dict[str, Any]:
    """Send weekly competitive intelligence digest via Resend for high-severity alerts."""

    api_key = os.environ.get("RESEND_API_KEY", "")
    digest_to = DIGEST_TO
    if not digest_to or not api_key:
        LOG.warning("task_send_digest: DIGEST_TO or RESEND_API_KEY not set — skipping")
        return {"sent": False}

    # R0: Replaced SQL ORDER BY created_at DESC LIMIT 20 with Python sorting/slicing due to kotoba client shim limitations.
    all_alerts = get_kotoba_client().select_where(
        "vertex_compintel_alert",
        "severity",
        "high",
        columns=["competitor_id", "dimension", "summary", "severity"]
    )
    all_alerts.sort(key=lambda a: a.get("created_at", ""), reverse=True)
    alerts = all_alerts[:20]
    if not alerts:
        return {"sent": False}

    body_lines = ["# Weekly Competitive Intelligence Digest\n"]
    for a in alerts:
        body_lines.append(f"**[HIGH] {a.get('competitor_id','')} / {a.get('dimension','')}**")
        body_lines.append(a.get("summary", ""))
        body_lines.append("")
    body_text = "\n".join(body_lines)

    resend_email_id = ""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "from": RESEND_FROM,
                    "to": [digest_to],
                    "subject": "Weekly Competitive Intelligence Digest",
                    "text": body_text,
                },
            )
            if r.status_code in (200, 201):
                resend_email_id = r.json().get("id", "")
            else:
                LOG.error("task_send_digest: resend error %d: %s", r.status_code, r.text[:200])
    except Exception as exc:
        LOG.error("task_send_digest: http error: %s", exc)

    LOG.info("task_send_digest: sent=%s email_id=%s", bool(resend_email_id), resend_email_id)
    return {"sent": bool(resend_email_id), "resendEmailId": resend_email_id}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    load_env_file()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    worker = _make_worker()

    worker.task(task_type="compintel.run_research_agent", timeout_ms=300_000, max_jobs_to_activate=3)(
        task_run_research_agent
    )
    worker.task(task_type="compintel.score_threats", timeout_ms=60_000, max_jobs_to_activate=5)(
        task_score_threats
    )
    worker.task(task_type="compintel.send_digest", timeout_ms=60_000, max_jobs_to_activate=5)(
        task_send_digest
    )

    LOG.info("compintel worker started — listening on Zeebe")
    asyncio.run(worker.work())


if __name__ == "__main__":
    main()
