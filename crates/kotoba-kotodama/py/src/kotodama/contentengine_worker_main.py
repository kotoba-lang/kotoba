"""
Zeebe worker for contentengine (Personalized Content Engine) — ADR-2605072000.

LangGraph intra-job personalization loop:
  load_cohort_profile → match_sources → draft_content → rank_variants
  → quality_gate → store_content

LangServer job types:
  contentengine.run_content_agent   — LangGraph loop (180s)
  contentengine.create_sponsor_slot — XRPC to ads.etzhayyim.com createCampaign (30s)

Cohort-first personalization — no individual PII stored (ADR-0018, sensitivity_ord=0).
Sources: vertex_news_article + vertex_narou_chapter (existing graph data).

Run:
  python -m kotodama.contentengine_worker_main

Env:
  AGENTGATEWAY_MCP_URL      — LangServer AgentGateway URL (default 127.0.0.1:8080)
  RW_URL             — RisingWave postgres URL
  ANTHROPIC_API_KEY
  ADS_XRPC_URL       — ads.etzhayyim.com base (default https://adsm4d5c.etzhayyim.com)
  CONTENT_QUALITY_THRESHOLD — min quality score (default 0.65)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Annotated, Any, TypedDict

import httpx
from langchain_anthropic import ChatAnthropic
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from kotodama.langserver_compat import LangServerWorker, create_langserver_channel

from kotodama.kotoba_datomic import get_kotoba_client
from kotodama.local_agent_env import load_env_file
from kotodama.llm import resolve_model_id

LOG = logging.getLogger("contentengine_worker")

CONTENTENGINE_DID = "did:web:contentengine.etzhayyim.com"
ADS_XRPC_URL = os.environ.get("ADS_XRPC_URL", "https://adsm4d5c.etzhayyim.com")
QUALITY_THRESHOLD = float(os.environ.get("CONTENT_QUALITY_THRESHOLD", "0.65"))


# ---------------------------------------------------------------------------
# LangGraph state
# ---------------------------------------------------------------------------

class ContentState(TypedDict):
    messages: Annotated[list[Any], add_messages]
    content_id: str
    cohort_name: str
    content_type: str
    topic: str
    tone: str
    max_words: int
    # profile
    cohort_interests: list[str]
    reading_level: str
    industry_context: str
    # source signals
    source_snippets: str
    # draft
    title: str
    body: str
    quality_score: float
    relevance_score: float
    retry_count: int
    stored: bool


# ---------------------------------------------------------------------------
# LangGraph nodes
# ---------------------------------------------------------------------------

def _llm() -> ChatAnthropic:
    model_id = resolve_model_id("general")
    return ChatAnthropic(model=model_id, temperature=0.6, max_tokens=2048)


def load_cohort_profile(state: ContentState) -> dict[str, Any]:
    """Load cohort profile from vertex_contentengine_cohort_profile."""
    cohort_name = state.get("cohort_name", "")

    client = get_kotoba_client()
    row = client.select_first_where(
        "vertex_contentengine_cohort_profile", "cohort_name", cohort_name,
        columns=["interests", "reading_level", "preferred_formats", "industry_context"]
    )
    interests: list[str] = []
    reading_level = "intermediate"
    industry_context = ""
    if row:
        try:
            interests_raw = row.get("interests", "") or ""
            interests = json.loads(interests_raw) if interests_raw else []
        except Exception:
            interests = []
        reading_level = row.get("reading_level", "intermediate") or "intermediate"
        industry_context = row.get("industry_context", "") or ""

    LOG.info("load_cohort_profile: cohort=%s interests=%d", cohort_name, len(interests))
    return {
        "cohort_interests": interests,
        "reading_level": reading_level,
        "industry_context": industry_context,
    }


def match_sources(state: ContentState) -> dict[str, Any]:
    """Find relevant news + narou content as writing signals."""
    topic = state.get("topic", "")
    interests = state.get("cohort_interests", [])

    client = get_kotoba_client()
    # query news articles
    # R0: ILIKE, ORDER BY, and LIMIT handled in Python
    all_news_rows = client.select_where(
        "vertex_news_article", "label", "NewsArticle", # Fetch a broad set
        columns=["title", "body_text", "created_at"], limit=2000
    )
    news_rows = [
        row for row in all_news_rows if topic[:50].lower() in row.get("title", "").lower()
    ]
    news_rows.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    news_rows = news_rows[:5]
    # query narou chapters if creative content
    narou_rows: list[dict[str, Any]] = []
    if state.get("content_type") in ("blog_post", "social_thread") and interests:
        interest_term = interests[0] if interests else topic
        # R0: ILIKE, ORDER BY, and LIMIT handled in Python
        all_narou_rows = client.select_where(
            "vertex_narou_chapter", "label", "NarouChapter", # Fetch a broad set
            columns=["title", "body_text", "created_at"], limit=2000
        )
        narou_rows = [
            row for row in all_narou_rows if interest_term[:50].lower() in row.get("title", "").lower()
        ]
        narou_rows.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        narou_rows = narou_rows[:3]

    snippets = []
    for r in (news_rows or []):
        t = r.get("title", "")
        b = (r.get("body_text") or "")[:200]
        snippets.append(f"[News] {t}: {b}")
    for r in (narou_rows or []):
        t = r.get("title", "")
        b = (r.get("body_text") or "")[:150]
        snippets.append(f"[Narou] {t}: {b}")

    source_text = "\n".join(snippets) if snippets else "(no matching sources found)"
    LOG.info("match_sources: topic=%r news=%d narou=%d", topic[:30], len(news_rows or []), len(narou_rows))
    return {"source_snippets": source_text}


def draft_content(state: ContentState) -> dict[str, Any]:
    """LLM draft personalized content for the cohort."""
    llm = _llm()
    cohort_name = state.get("cohort_name", "general audience")
    topic = state.get("topic", "")
    tone = state.get("tone", "professional")
    content_type = state.get("content_type", "blog_post")
    max_words = state.get("max_words", 500)
    reading_level = state.get("reading_level", "intermediate")
    industry_context = state.get("industry_context", "")
    interests = state.get("cohort_interests", [])
    sources = state.get("source_snippets", "")

    type_instruction = {
        "blog_post": f"Write a {tone} blog post",
        "social_thread": "Write a Twitter/X thread (3-5 tweets separated by ---)",
        "email_body": f"Write a {tone} email body",
        "report_summary": f"Write a {tone} executive summary",
    }.get(content_type, f"Write a {tone} piece")

    prompt = (
        f"{type_instruction} about: {topic}\n"
        f"Target cohort: {cohort_name}\n"
        f"Reading level: {reading_level}\n"
        f"Industry context: {industry_context}\n"
        f"Cohort interests: {', '.join(interests[:5])}\n"
        f"Reference signals:\n{sources[:1500]}\n\n"
        f"Maximum {max_words} words.\n"
        'Respond with JSON: {"title": "...", "body": "..."}'
    )

    resp = llm.invoke(prompt)
    raw = str(resp.content).strip()
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        parsed = json.loads(raw[start:end])
        title = str(parsed.get("title", ""))
        body = str(parsed.get("body", ""))
    except Exception:
        title = topic[:100]
        body = raw

    LOG.info("draft_content: title=%r words=%d", title[:40], len(body.split()))
    return {"title": title, "body": body}


def rank_variants(state: ContentState) -> dict[str, Any]:
    """Score content for quality and cohort relevance."""
    title = state.get("title", "")
    body = state.get("body", "")
    interests = state.get("cohort_interests", [])
    topic = state.get("topic", "")
    max_words = state.get("max_words", 500)

    word_count = len(body.split())
    quality_score = 0.4
    if title and body:
        quality_score += 0.15
    if word_count >= 50:
        quality_score += 0.10
    if word_count <= max_words * 1.2:
        quality_score += 0.10
    if topic.lower() in body.lower():
        quality_score += 0.10

    relevance_score = 0.5
    if interests:
        matched = sum(1 for i in interests[:5] if i.lower() in body.lower())
        relevance_score = min(1.0, 0.5 + matched * 0.1)

    LOG.info("rank_variants: quality=%.2f relevance=%.2f", quality_score, relevance_score)
    return {
        "quality_score": round(quality_score, 3),
        "relevance_score": round(relevance_score, 3),
    }


def quality_gate_node(state: ContentState) -> dict[str, Any]:
    return {}


def store_content(state: ContentState) -> dict[str, Any]:
    """INSERT content to vertex_contentengine_content (no onConflict — PK implicit)."""
    content_id = state["content_id"]
    now = datetime.now(timezone.utc).isoformat()
    vertex_id = hashlib.sha256(f"content:{content_id}".encode()).hexdigest()

    client = get_kotoba_client()
    row_dict = {
        "vertex_id": vertex_id,
        "record_id": f"contentengine:content:{content_id}",
        "owner_did": CONTENTENGINE_DID,
        "label": "ContentEngineContent",
        "status": "ready",
        "agent_did": CONTENTENGINE_DID,
        "created_at": now,
        "updated_at": now,
        "sensitivity_ord": 0,
        "content_id": content_id,
        "cohort_name": state.get("cohort_name", ""),
        "content_type": state.get("content_type", ""),
        "topic": state.get("topic", ""),
        "tone": state.get("tone", ""),
        "title": state.get("title", ""),
        "body": state.get("body", ""),
        "quality_score": state.get("quality_score", 0.0),
        "relevance_score": state.get("relevance_score", 0.0),
        "include_sponsor_slot": False,
    }
    client.insert_row("vertex_contentengine_content", row_dict)

    LOG.info("store_content: content_id=%s quality=%.2f relevance=%.2f",
             content_id, state.get("quality_score", 0), state.get("relevance_score", 0))
    return {"stored": True}


def should_retry_content(state: ContentState) -> str:
    score = state.get("quality_score", 0.0)
    retries = state.get("retry_count", 0)
    if score < QUALITY_THRESHOLD and retries < 1:
        return "retry"
    return "store"


# ---------------------------------------------------------------------------
# Build LangGraph
# ---------------------------------------------------------------------------

def _build_graph() -> Any:
    g: StateGraph = StateGraph(ContentState)
    g.add_node("load_cohort_profile", load_cohort_profile)
    g.add_node("match_sources", match_sources)
    g.add_node("draft_content", draft_content)
    g.add_node("rank_variants", rank_variants)
    g.add_node("quality_gate_node", quality_gate_node)
    g.add_node("store_content", store_content)

    g.add_edge(START, "load_cohort_profile")
    g.add_edge("load_cohort_profile", "match_sources")
    g.add_edge("match_sources", "draft_content")
    g.add_edge("draft_content", "rank_variants")
    g.add_edge("rank_variants", "quality_gate_node")
    g.add_conditional_edges(
        "quality_gate_node",
        should_retry_content,
        {"retry": "draft_content", "store": "store_content"},
    )
    g.add_edge("store_content", END)
    return g.compile()


_GRAPH = _build_graph()


# ---------------------------------------------------------------------------
# LangServer handlers
# ---------------------------------------------------------------------------

def _make_worker() -> LangServerWorker:
    gateway = os.environ.get("AGENTGATEWAY_MCP_URL", "127.0.0.1:8080")
    channel = create_langserver_channel(grpc_address=gateway)
    return LangServerWorker(channel)


async def task_run_content_agent(
    content_id: str = "",
    cohort_name: str = "",
    content_type: str = "blog_post",
    topic: str = "",
    tone: str = "professional",
    max_words: int = 500,
    include_sponsor_slot: bool = False,
    **_: Any,
) -> dict[str, Any]:
    """LangGraph personalized content generation loop."""
    init_state: ContentState = {
        "messages": [],
        "content_id": content_id,
        "cohort_name": cohort_name,
        "content_type": content_type,
        "topic": topic,
        "tone": tone,
        "max_words": max_words,
        "cohort_interests": [],
        "reading_level": "intermediate",
        "industry_context": "",
        "source_snippets": "",
        "title": "",
        "body": "",
        "quality_score": 0.0,
        "relevance_score": 0.0,
        "retry_count": 0,
        "stored": False,
    }
    final = await asyncio.to_thread(_GRAPH.invoke, init_state)
    return {
        "title": final.get("title", ""),
        "qualityScore": final.get("quality_score", 0.0),
        "relevanceScore": final.get("relevance_score", 0.0),
        "includeSponsorSlot": include_sponsor_slot,
    }


async def task_create_sponsor_slot(
    content_id: str = "",
    cohort_name: str = "",
    topic: str = "",
    **_: Any,
) -> dict[str, Any]:
    """Optional XRPC call to ads.etzhayyim.com createCampaign."""
    ad_campaign_id = ""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                f"{ADS_XRPC_URL}/xrpc/com.etzhayyim.apps.ads.createCampaign",
                json={
                    "campaignName": f"Content: {topic[:80]}",
                    "targetAudience": cohort_name,
                    "sourceActor": CONTENTENGINE_DID,
                    "sourceEntityId": content_id,
                },
                headers={"content-type": "application/json"},
            )
            if r.status_code in (200, 201):
                ad_campaign_id = r.json().get("campaignId", "")
    except Exception as exc:
        LOG.warning("task_create_sponsor_slot: ads call failed: %s", exc)

    if ad_campaign_id:
        now = datetime.now(timezone.utc).isoformat()
        vid = hashlib.sha256(f"content:{content_id}".encode()).hexdigest()

        client = get_kotoba_client()
        # Retrieve existing row to update
        existing_row = client.select_first_where("vertex_contentengine_content", "vertex_id", vid)

        if existing_row:
            existing_row["ad_campaign_id"] = ad_campaign_id
            existing_row["include_sponsor_slot"] = True
            existing_row["updated_at"] = now
            client.insert_row("vertex_contentengine_content", existing_row) # Upsert with updated values

    LOG.info("task_create_sponsor_slot: content_id=%s ad_campaign_id=%s", content_id, ad_campaign_id)
    return {"adCampaignId": ad_campaign_id}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    load_env_file()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    worker = _make_worker()

    worker.task(task_type="contentengine.run_content_agent", timeout_ms=180_000, max_jobs_to_activate=5)(
        task_run_content_agent
    )
    worker.task(task_type="contentengine.create_sponsor_slot", timeout_ms=30_000, max_jobs_to_activate=10)(
        task_create_sponsor_slot
    )

    LOG.info("contentengine worker started — listening on Zeebe")
    asyncio.run(worker.work())


if __name__ == "__main__":
    main()
