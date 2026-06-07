"""
Zeebe worker for newsletter (Newsletter Factory) — ADR-2605072000.

LangGraph intra-job curation loop:
  ingest_signals → filter_relevant → rank_content → draft_newsletter
  → personalize → quality_gate → store_campaign

LangServer job types:
  newsletter.run_curation_agent  — LangGraph loop (~60–120s)
  newsletter.send_via_resend     — Resend batch send per subscriber
  newsletter.create_sponsor_slot — XRPC to ads.etzhayyim.com createCampaign

Weekly schedule: Zeebe BPMN timer "0 0 * * 2" (Tuesday 09:00 JST).

Run:
  python -m kotodama.newsletter_worker_main

Env:
  AGENTGATEWAY_MCP_URL      — LangServer AgentGateway URL (default 127.0.0.1:8080)
  RW_URL             — RisingWave postgres URL
  ANTHROPIC_API_KEY
  RESEND_API_KEY
  RESEND_FROM        — sender address (default newsletter@etzhayyim.com)
  ADS_XRPC_URL       — ads.etzhayyim.com base (default https://adsm4d5c.etzhayyim.com)
  NEWS_XRPC_URL      — news.etzhayyim.com base (default https://news.etzhayyim.com)
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

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

from kotodama.db_sync import fetch_all, fetch_one, sync_cursor
from kotodama.local_agent_env import load_env_file, load_keychain_secret
from kotodama.llm import resolve_model_id

LOG = logging.getLogger("newsletter_worker")

NEWSLETTER_DID = "did:web:newsletter.etzhayyim.com"
ADS_DID = "did:web:ads.etzhayyim.com"

QUALITY_THRESHOLD = float(os.environ.get("NEWSLETTER_QUALITY_THRESHOLD", "0.7"))
RESEND_FROM = os.environ.get("RESEND_FROM", "newsletter@etzhayyim.com")
ADS_XRPC_URL = os.environ.get("ADS_XRPC_URL", "https://adsm4d5c.etzhayyim.com")
NEWS_XRPC_URL = os.environ.get("NEWS_XRPC_URL", "https://news.etzhayyim.com")
MAX_SIGNALS = int(os.environ.get("NEWSLETTER_MAX_SIGNALS", "50"))
TOP_N_SIGNALS = int(os.environ.get("NEWSLETTER_TOP_N", "10"))


# ─── helpers ──────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid(prefix: str) -> str:
    digest = hashlib.sha256(f"{prefix}{time.time_ns()}".encode()).hexdigest()[:12]
    return f"{prefix}-{digest}"


# ─── LangGraph state ──────────────────────────────────────────────────────


class NewsletterState(TypedDict, total=False):
    campaign_id: str
    campaign_name: str
    topic: str
    cohort_name: str
    include_ad_slot: bool
    subject_line_override: str
    # populated by nodes
    raw_signals: list[dict[str, Any]]
    filtered_signals: list[dict[str, Any]]
    ranked_signals: list[dict[str, Any]]
    subject_line: str
    body_html: str
    quality_score: float
    retry_count: int
    messages: Annotated[list, add_messages]


# ─── LangGraph nodes ──────────────────────────────────────────────────────


async def node_init_defaults(state: NewsletterState) -> dict[str, Any]:
    """Seed every state field with a safe default before the rest of the chain
    (LangGraph initial state contains only what the caller passed)."""
    return {
        "campaign_id": state.get("campaign_id") or _uid("campaign"),
        "campaign_name": state.get("campaign_name") or "untitled",
        "topic": state.get("topic") or "",
        "cohort_name": state.get("cohort_name") or "",
        "include_ad_slot": bool(state.get("include_ad_slot", False)),
        "subject_line_override": state.get("subject_line_override") or "",
        "raw_signals": state.get("raw_signals") or [],
        "filtered_signals": state.get("filtered_signals") or [],
        "ranked_signals": state.get("ranked_signals") or [],
        "subject_line": state.get("subject_line") or "",
        "body_html": state.get("body_html") or "",
        "quality_score": float(state.get("quality_score") or 0.0),
        "retry_count": int(state.get("retry_count") or 0),
    }


async def node_ingest_signals(state: NewsletterState) -> dict[str, Any]:
    """Pull recent articles from news.etzhayyim.com and narou.etzhayyim.com via RisingWave.

    Sources may not exist yet (vertex_news_article is reserved for future
    ingest); a missing table is treated as zero signals, not a fatal error.
    """
    def _safe_fetch(sql: str) -> list[tuple]:
        try:
            return fetch_all(sql, ())
        except Exception as exc:
            LOG.info("ingest source unavailable, skipping: %s", str(exc)[:120])
            return []

    def _fetch() -> list[dict[str, Any]]:
        rows = _safe_fetch(
            f"""
            SELECT vertex_id, label, value_json, created_at
            FROM vertex_news_article
            WHERE created_at > NOW() - INTERVAL '7 days'
            ORDER BY created_at DESC
            LIMIT {int(MAX_SIGNALS)}
            """
        )
        signals = []
        for r in rows:
            try:
                meta = json.loads(r[2] or "{}")
                signals.append({
                    "id": r[0],
                    "source": "news.etzhayyim.com",
                    "title": meta.get("title", ""),
                    "summary": meta.get("summary", ""),
                    "url": meta.get("url", ""),
                })
            except Exception:
                pass
        return signals

    def _fetch_narou() -> list[dict[str, Any]]:
        rows = _safe_fetch(
            """
            SELECT vertex_id, label, value_json, created_at
            FROM vertex_narou_chapter
            WHERE created_at > NOW() - INTERVAL '7 days'
            ORDER BY created_at DESC
            LIMIT 20
            """
        )
        signals = []
        for r in rows:
            try:
                meta = json.loads(r[2] or "{}")
                signals.append({
                    "id": r[0],
                    "source": "narou.etzhayyim.com",
                    "title": meta.get("title", ""),
                    "summary": meta.get("summary", meta.get("body", ""))[:300],
                    "url": "",
                })
            except Exception:
                pass
        return signals

    loop = asyncio.get_event_loop()
    news = await loop.run_in_executor(None, _fetch)
    narou = await loop.run_in_executor(None, _fetch_narou)
    return {"raw_signals": news + narou}


async def node_filter_relevant(state: NewsletterState) -> dict[str, Any]:
    """Filter signals by relevance to campaign topic using Claude."""
    if not state["raw_signals"]:
        return {"filtered_signals": []}

    llm = ChatAnthropic(model=resolve_model_id("default"))
    signals_txt = "\n".join(
        f"{i+1}. [{s['source']}] {s['title']}: {s['summary'][:150]}"
        for i, s in enumerate(state["raw_signals"][:30])
    )
    prompt = f"""Topic: {state['topic']}
Cohort: {state['cohort_name'] or 'general business audience'}

Articles to filter:
{signals_txt}

Return a JSON array of 1-based indices that are relevant to the topic and cohort.
Example: [1, 3, 7, 12]
Return ONLY the JSON array, no explanation.
"""
    response = await llm.ainvoke(prompt)
    try:
        raw = str(response.content).strip()
        start, end = raw.find("["), raw.rfind("]") + 1
        indices: list[int] = json.loads(raw[start:end])
        filtered = [state["raw_signals"][i - 1] for i in indices if 1 <= i <= len(state["raw_signals"])]
    except Exception:
        filtered = state["raw_signals"][:10]

    return {"filtered_signals": filtered}


async def node_rank_content(state: NewsletterState) -> dict[str, Any]:
    """Rank filtered signals by engagement potential."""
    if not state["filtered_signals"]:
        return {"ranked_signals": []}

    llm = ChatAnthropic(model=resolve_model_id("default"))
    signals_txt = "\n".join(
        f"{i+1}. {s['title']}: {s['summary'][:100]}"
        for i, s in enumerate(state["filtered_signals"][:20])
    )
    prompt = f"""Rank these articles by engagement potential for a newsletter (1=highest).
Topic: {state['topic']} | Cohort: {state['cohort_name'] or 'general'}

{signals_txt}

Return JSON: [{{"rank": 1, "index": 3, "reason": "..."}}, ...]
Limit to top {TOP_N_SIGNALS}. Return ONLY JSON array.
"""
    response = await llm.ainvoke(prompt)
    try:
        raw = str(response.content).strip()
        start, end = raw.find("["), raw.rfind("]") + 1
        ranked_meta: list[dict] = json.loads(raw[start:end])
        ranked = [
            state["filtered_signals"][m["index"] - 1]
            for m in ranked_meta
            if 1 <= m.get("index", 0) <= len(state["filtered_signals"])
        ]
    except Exception:
        ranked = state["filtered_signals"][:TOP_N_SIGNALS]

    return {"ranked_signals": ranked}


async def node_draft_newsletter(state: NewsletterState) -> dict[str, Any]:
    """Draft the newsletter HTML and subject line using Claude."""
    if not state.get("ranked_signals"):
        return {
            "subject_line": state.get("subject_line_override") or "Weekly newsletter (no content)",
            "body_html": "<p>No content available for this period.</p>",
        }
    llm = ChatAnthropic(model=resolve_model_id("default"))

    articles_txt = "\n".join(
        f"- **{s['title']}** ({s['source']}): {s['summary'][:200]}"
        for s in state["ranked_signals"]
    )
    subject_instruction = (
        f'Use this subject line: "{state["subject_line_override"]}"'
        if state["subject_line_override"]
        else "Generate a compelling subject line (max 60 chars)"
    )

    prompt = f"""Write a professional weekly newsletter in HTML format.

Topic: {state['topic']}
Audience: {state['cohort_name'] or 'business professionals'}
{subject_instruction}

Content to include:
{articles_txt}

Generate:
1. Subject line (JSON key: "subject")
2. HTML body (JSON key: "body") with:
   - Brief editorial intro (2-3 sentences)
   - Featured articles section (each with title, 1-sentence description, "Read more →" link if URL available)
   - Brief closing call-to-action
   - Minimal, clean HTML (no inline CSS beyond font-family and colors)

Return JSON: {{"subject": "...", "body": "<html>...</html>"}}
"""
    response = await llm.ainvoke(prompt)
    try:
        raw = str(response.content).strip()
        start, end = raw.find("{"), raw.rfind("}") + 1
        parsed = json.loads(raw[start:end])
        subject = parsed.get("subject", f"Weekly Digest: {state['topic'][:40]}")
        body = parsed.get("body", "<p>Newsletter content</p>")
    except Exception:
        subject = f"Weekly Digest: {state['topic'][:40]}"
        body = "<p>" + articles_txt.replace("\n", "<br>") + "</p>"

    return {"subject_line": subject, "body_html": body}


async def node_personalize(state: NewsletterState) -> dict[str, Any]:
    """Add cohort-specific personalization to subject and body."""
    if not state.get("cohort_name") or not state.get("body_html"):
        return {}

    llm = ChatAnthropic(model=resolve_model_id("default"))
    prompt = f"""Personalize this newsletter subject line for cohort: {state['cohort_name']}

Current subject: {state['subject_line']}
Cohort context: APQC PCF Market & Sell segment — sales and marketing professionals in various industries.

Return ONLY the personalized subject line (≤60 chars), no explanation.
"""
    response = await llm.ainvoke(prompt)
    personalized_subject = str(response.content).strip().strip('"')
    if len(personalized_subject) > 60:
        personalized_subject = state["subject_line"]

    return {"subject_line": personalized_subject}


async def node_quality_gate(state: NewsletterState) -> dict[str, Any]:
    """Score newsletter quality via the reusable judge subgraph.

    Delegates to `_subgraphs.judge.arun_judge` (ADR-2605080000 §6-Layer
    composition). Empty newsletter scores 0 and proceeds to store.
    """
    if not state.get("body_html") or not state.get("ranked_signals"):
        return {"quality_score": 0.0, "retry_count": 99}

    from kotodama.langgraph_graphs._subgraphs.judge import arun_judge

    judge = await arun_judge(
        persona="newsletter editor",
        subject=f"newsletter '{state['subject_line']}' ({len(state['body_html'])} chars, "
                f"{len(state['ranked_signals'])} signals)",
        signals={
            "subject_line": state["subject_line"],
            "body_sample": state["body_html"][:400],
            "topic": state.get("topic", ""),
            "cohort": state.get("cohort_name", ""),
        },
        prompt_suffix=(
            "Criteria weights: engagement (0.3), topic relevance (0.3), "
            'clarity (0.2), completeness (0.2). Return JSON only: '
            '{"score": 0.0-1.0, "summary": "1 sentence why"}'
        ),
    )
    return {"quality_score": float(judge.get("score", 0.5))}


async def node_store_campaign(state: NewsletterState) -> dict[str, Any]:
    """Persist campaign to RisingWave vertex_newsletter_campaign."""
    def _run() -> None:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                """
                INSERT INTO vertex_newsletter_campaign (
                  vertex_id, record_id, owner_did, label, status,
                  campaign_id, campaign_name, topic, cohort_name,
                  subject_line, body_html, quality_score,
                  include_ad_slot, created_at, updated_at, sensitivity_ord
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    f"at://{NEWSLETTER_DID}/com.etzhayyim.apps.newsletter.campaign/{state['campaign_id']}",
                    state["campaign_id"],
                    NEWSLETTER_DID,
                    "newsletter_campaign",
                    "curated",
                    state["campaign_id"],
                    state["campaign_name"],
                    state["topic"][:500],
                    state["cohort_name"],
                    state["subject_line"],
                    state["body_html"][:32000],
                    state["quality_score"],
                    state["include_ad_slot"],
                    _now(),
                    _now(),
                    2,
                ),
            )
    await asyncio.get_event_loop().run_in_executor(None, _run)
    return {}


def should_retry_newsletter(state: NewsletterState) -> str:
    if state["quality_score"] >= QUALITY_THRESHOLD:
        return "store"
    if state.get("retry_count", 0) >= 1:
        LOG.warning("newsletter quality gate failed (score=%.2f), storing anyway", state["quality_score"])
        return "store"
    return "retry"


# ─── Build LangGraph ──────────────────────────────────────────────────────


def build_newsletter_graph():
    g = StateGraph(NewsletterState)
    g.add_node("init_defaults", node_init_defaults)
    g.add_node("ingest_signals", node_ingest_signals)
    g.add_node("filter_relevant", node_filter_relevant)
    g.add_node("rank_content", node_rank_content)
    g.add_node("draft_newsletter", node_draft_newsletter)
    g.add_node("personalize", node_personalize)
    g.add_node("quality_gate", node_quality_gate)
    g.add_node("store_campaign", node_store_campaign)

    g.add_edge(START, "init_defaults")
    g.add_edge("init_defaults", "ingest_signals")
    g.add_edge("ingest_signals", "filter_relevant")
    g.add_edge("filter_relevant", "rank_content")
    g.add_edge("rank_content", "draft_newsletter")
    g.add_edge("draft_newsletter", "personalize")
    g.add_edge("personalize", "quality_gate")
    g.add_conditional_edges(
        "quality_gate",
        should_retry_newsletter,
        {"store": "store_campaign", "retry": "draft_newsletter"},
    )
    g.add_edge("store_campaign", END)
    return g.compile(checkpointer=None)


NEWSLETTER_GRAPH = build_newsletter_graph()


# ─── newsletter.run_curation_agent ────────────────────────────────────────


async def task_run_curation_agent(
    campaignId: str,
    campaignName: str,
    topic: str,
    cohortName: str = "",
    includeAdSlot: bool = False,
    subjectLine: str = "",
    **_: Any,
) -> dict[str, Any]:
    LOG.info("run_curation_agent start campaignId=%s topic=%s", campaignId, topic[:50])

    initial: NewsletterState = {
        "campaign_id": campaignId,
        "campaign_name": campaignName,
        "topic": topic,
        "cohort_name": cohortName,
        "include_ad_slot": includeAdSlot,
        "subject_line_override": subjectLine,
        "raw_signals": [],
        "filtered_signals": [],
        "ranked_signals": [],
        "subject_line": "",
        "body_html": "",
        "quality_score": 0.0,
        "retry_count": 0,
        "messages": [],
    }

    final = await NEWSLETTER_GRAPH.ainvoke(initial)
    LOG.info("run_curation_agent done campaignId=%s score=%.2f", campaignId, final.get("quality_score", 0))
    return {
        "campaignId": campaignId,
        "qualityScore": final.get("quality_score", 0.0),
        "subjectLine": final.get("subject_line", ""),
        "signalCount": len(final.get("ranked_signals", [])),
    }


# ─── newsletter.send_via_resend ───────────────────────────────────────────


async def task_send_via_resend(
    campaignId: str,
    **_: Any,
) -> dict[str, Any]:
    def _fetch_campaign() -> dict[str, Any] | None:
        return fetch_one(
            "SELECT campaign_name, subject_line, body_html FROM vertex_newsletter_campaign WHERE campaign_id = %s",
            (campaignId,),
        )

    def _fetch_subscribers(cohort: str) -> list[tuple]:
        if cohort:
            return fetch_all(
                "SELECT record_id, email, subscriber_name FROM vertex_newsletter_subscriber "
                "WHERE status = 'active' AND cohort_name = %s LIMIT 1000",
                (cohort,),
            )
        return fetch_all(
            "SELECT record_id, email, subscriber_name FROM vertex_newsletter_subscriber "
            "WHERE status = 'active' LIMIT 1000",
            (),
        )

    loop = asyncio.get_event_loop()
    row = await loop.run_in_executor(None, _fetch_campaign)
    if not row:
        raise ValueError(f"campaign not found: {campaignId}")

    campaign_name, subject_line, body_html = row[0], row[1], row[2]

    cohort_row = fetch_one(
        "SELECT cohort_name FROM vertex_newsletter_campaign WHERE campaign_id = %s", (campaignId,)
    )
    cohort = cohort_row[0] if cohort_row else ""

    subscribers = await loop.run_in_executor(None, _fetch_subscribers, cohort)
    if not subscribers:
        LOG.info("send_via_resend: no subscribers for campaignId=%s", campaignId)
        return {"status": "skipped", "recipientCount": 0, "reason": "no subscribers"}

    resend_key = os.environ.get("RESEND_API_KEY", "")
    if not resend_key:
        LOG.warning("RESEND_API_KEY not set, skipping send")
        return {"status": "skipped", "recipientCount": 0, "reason": "no RESEND_API_KEY"}

    sent_count = 0
    async with httpx.AsyncClient() as client:
        for sub_id, email, name in subscribers:
            greeting = f"Hi {name or 'there'},"
            personalized_html = body_html.replace("<body>", f"<body><p>{greeting}</p>", 1)
            if "<body>" not in body_html:
                personalized_html = f"<p>{greeting}</p>" + body_html

            try:
                resp = await client.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
                    json={
                        "from": RESEND_FROM,
                        "to": [email],
                        "subject": subject_line,
                        "html": personalized_html,
                    },
                    timeout=15,
                )
                if resp.status_code == 200:
                    email_id = resp.json().get("id", "")
                    sent_count += 1

                    def _record(eid: str, sid: str) -> None:
                        if True:
                            client = get_kotoba_client()
                            _res = client.q(
                                "INSERT INTO edge_newsletter_sent "
                                "(edge_id,src_vid,dst_vid,relation_kind,campaign_id,subscriber_id,resend_email_id,created_at,updated_at,owner_did,sensitivity_ord) "
                                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                                (
                                    _uid("ens"),
                                    f"at://{NEWSLETTER_DID}/com.etzhayyim.apps.newsletter.campaign/{campaignId}",
                                    f"at://{NEWSLETTER_DID}/com.etzhayyim.apps.newsletter.subscriber/{sid}",
                                    "sent_to",
                                    campaignId, sid, eid, _now(), _now(), NEWSLETTER_DID, 3,
                                ),
                            )
                    await loop.run_in_executor(None, _record, email_id, sub_id)
            except Exception as e:
                LOG.warning("send failed for subscriber %s: %s", sub_id, e)

    sent_at = _now()

    def _mark_sent(count: int) -> None:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                "UPDATE vertex_newsletter_campaign SET status='sent', recipient_count=%s, sent_at=%s, updated_at=%s "
                "WHERE campaign_id=%s",
                (count, sent_at, sent_at, campaignId),
            )
    await loop.run_in_executor(None, _mark_sent, sent_count)

    LOG.info("send_via_resend done campaignId=%s sent=%d", campaignId, sent_count)
    return {"status": "sent", "recipientCount": sent_count, "sentAt": sent_at}


# ─── newsletter.create_sponsor_slot ──────────────────────────────────────


async def task_create_sponsor_slot(
    campaignId: str,
    campaignName: str,
    **_: Any,
) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{ADS_XRPC_URL}/xrpc/com.etzhayyim.apps.ads.createCampaign",
            json={
                "name": f"newsletter-{campaignId[:8]} sponsor",
                "description": f"Sponsor slot for newsletter campaign: {campaignName}",
                "advertiser": "etzhayyim Newsletter",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

    ad_campaign_id = data.get("campaignId", "")

    def _link() -> None:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                "UPDATE vertex_newsletter_campaign SET ad_campaign_id=%s, updated_at=%s WHERE campaign_id=%s",
                (ad_campaign_id, _now(), campaignId),
            )
    await asyncio.get_event_loop().run_in_executor(None, _link)
    LOG.info("create_sponsor_slot done campaignId=%s adCampaignId=%s", campaignId, ad_campaign_id)
    return {"adCampaignId": ad_campaign_id}


# ─── main ─────────────────────────────────────────────────────────────────


async def main() -> None:
    load_env_file()
    for key, service, env_key in [
        ("ANTHROPIC_API_KEY", "etzhayyim.anthropic", "ANTHROPIC_API_KEY"),
        ("RESEND_API_KEY", "etzhayyim.resend", "RESEND_API_KEY"),
    ]:
        val = load_keychain_secret(key, service, env_key)
        if val:
            os.environ[env_key] = val

    gateway = os.environ.get("AGENTGATEWAY_MCP_URL", "127.0.0.1:8080")
    channel = create_langserver_channel(grpc_address=gateway)
    worker = LangServerWorker(channel)

    worker.task(task_type="newsletter.run_curation_agent", timeout_ms=180_000)(task_run_curation_agent)
    worker.task(task_type="newsletter.send_via_resend", timeout_ms=120_000)(task_send_via_resend)
    worker.task(task_type="newsletter.create_sponsor_slot", timeout_ms=30_000)(task_create_sponsor_slot)

    LOG.info("newsletter worker started (gateway=%s)", gateway)

    stop_event = asyncio.Event()
    import signal as _signal

    def _stop(*_: Any) -> None:
        stop_event.set()

    _signal.signal(_signal.SIGTERM, _stop)
    _signal.signal(_signal.SIGINT, _stop)
    await worker.work(stop_event=stop_event)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    asyncio.run(main())
