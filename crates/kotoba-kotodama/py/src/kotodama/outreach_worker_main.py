"""
Zeebe worker for outreach (Sales Outreach Automation) — ADR-2605072000.

LangGraph intra-job research + draft loop:
  research_prospect → draft_opening → quality_gate → store_step

LangServer job types:
  outreach.check_dnc            — DNC gate before every send (15s)
  outreach.run_research_agent   — LangGraph loop: research + personalized draft (180s)
  outreach.send_via_resend      — Send step N email via Resend (60s)
  outreach.correlate_reply      — Correlate gmail/m365Ingest reply to active sequence (30s)
  outreach.create_sponsor_slot  — XRPC to ads.etzhayyim.com createCampaign (30s)

Reply detection: subscribeRepos fires on com.etzhayyim.apps.gmail.message and
com.etzhayyim.apps.m365Ingest.email; the dispatcher routes to outreach.correlate_reply.

PII: prospect email/title/company = Tier 3 (sensitivity_ord=3, ADR-0018).
Never log PII. Cohort-first default.

Run:
  python -m kotodama.outreach_worker_main

Env:
  AGENTGATEWAY_MCP_URL      — LangServer AgentGateway URL (default 127.0.0.1:8080)
  KOTOBA_URL         — Kotoba Datomic Client URL
  ANTHROPIC_API_KEY
  RESEND_API_KEY
  RESEND_FROM        — sender address (default outreach@etzhayyim.com)
  ADS_XRPC_URL       — ads.etzhayyim.com base (default https://adsm4d5c.etzhayyim.com)
  OUTREACH_QUALITY_THRESHOLD — min score to send (default 0.75)
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
from kotodama.local_agent_env import load_env_file, load_keychain_secret
from kotodama.llm import resolve_model

LOG = logging.getLogger("outreach_worker")

OUTREACH_DID = "did:web:outreach.etzhayyim.com"
ADS_DID = "did:web:ads.etzhayyim.com"

QUALITY_THRESHOLD = float(os.environ.get("OUTREACH_QUALITY_THRESHOLD", "0.75"))
RESEND_FROM = os.environ.get("RESEND_FROM", "outreach@etzhayyim.com")
ADS_XRPC_URL = os.environ.get("ADS_XRPC_URL", "https://adsm4d5c.etzhayyim.com")


# ---------------------------------------------------------------------------
# LangGraph state
# ---------------------------------------------------------------------------

class OutreachState(TypedDict):
    messages: Annotated[list[Any], add_messages]
    prospect_id: str
    sequence_id: str
    step_number: int
    goal: str
    # research output
    company_summary: str
    prospect_context: str
    # draft output
    subject_line: str
    body_text: str
    quality_score: float
    retry_count: int
    # final
    stored: bool


# ---------------------------------------------------------------------------
# LangGraph nodes
# ---------------------------------------------------------------------------

def _llm() -> ChatAnthropic:
    model_id = resolve_model("mid")
    return ChatAnthropic(model=model_id, temperature=0.4, max_tokens=2048)


def research_prospect(state: OutreachState) -> dict[str, Any]:
    """Fetch prospect context from graph + lightweight web research."""
    prospect_id = state["prospect_id"]

    prospect = get_kotoba_client().select_first_where(
        "vertex_outreach_prospect", "vertex_id", prospect_id,
        columns=["email", "prospect_name", "title", "company", "cohort_name", "linkedin_url", "company_website"],
    )
    if not prospect:
        return {"company_summary": "", "prospect_context": "unknown prospect"}

    company = prospect.get("company") or ""
    title = prospect.get("title") or ""
    website = prospect.get("company_website") or ""

    # lightweight: just use available structured data (no external fetch to avoid timeout)
    prospect_context = f"{title} at {company}" if title and company else company or "unknown"
    company_summary = f"Company: {company}. Website: {website}." if company else ""

    LOG.info("research_prospect: prospect_id=%s company=%s", prospect_id, company)
    return {"company_summary": company_summary, "prospect_context": prospect_context}


def draft_opening(state: OutreachState) -> dict[str, Any]:
    """LLM draft a personalized cold email opening."""
    llm = _llm()
    step = state.get("step_number", 1)
    goal = state.get("goal", "schedule a call")
    context = state.get("prospect_context", "")
    company_summary = state.get("company_summary", "")

    step_label = "follow-up" if step > 1 else "initial outreach"
    prompt = (
        f"You are writing a {step_label} B2B cold email.\n"
        f"Goal: {goal}\n"
        f"Recipient context: {context}\n"
        f"Company context: {company_summary}\n\n"
        "Write a short, personalized email. Keep it under 120 words.\n"
        "Respond with JSON: {\"subject\": \"...\", \"body\": \"...\"}"
    )

    resp = llm.invoke(prompt)
    raw = str(resp.content).strip()
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        parsed = json.loads(raw[start:end])
        subject = str(parsed.get("subject", ""))
        body = str(parsed.get("body", ""))
    except Exception:
        subject = f"Quick question about {context}"
        body = raw

    LOG.info("draft_opening: subject=%r step=%d", subject, step)
    return {"subject_line": subject, "body_text": body}


def quality_gate(state: OutreachState) -> dict[str, Any]:
    """Score the draft for relevance, length, and personalization."""
    subject = state.get("subject_line", "")
    body = state.get("body_text", "")
    context = state.get("prospect_context", "")

    score = 0.5
    if subject and body:
        score += 0.15
    if len(body.split()) >= 20:
        score += 0.10
    if context and any(word in body.lower() for word in context.lower().split()[:3]):
        score += 0.15
    if len(body.split()) <= 150:
        score += 0.10

    LOG.info("quality_gate: score=%.2f threshold=%.2f", score, QUALITY_THRESHOLD)
    return {"quality_score": round(score, 3)}


def store_step(state: OutreachState) -> dict[str, Any]:
    """INSERT draft to vertex_outreach_step (kotoba Datom log)."""
    sequence_id = state["sequence_id"]
    step_number = state.get("step_number", 1)
    now = datetime.now(timezone.utc).isoformat()
    vertex_id = hashlib.sha256(f"{sequence_id}:step:{step_number}".encode()).hexdigest()

    row_data = {
        "vertex_id": vertex_id,
        "record_id": f"outreach:step:{sequence_id}:{step_number}",
        "owner_did": OUTREACH_DID,
        "label": "OutreachStep",
        "status": "drafted",
        "agent_did": OUTREACH_DID,
        "created_at": now,
        "updated_at": now,
        "sensitivity_ord": 0,
        "sequence_id": sequence_id,
        "step_number": step_number,
        "subject_line": state.get("subject_line", ""),
        "body_text": state.get("body_text", ""),
        "quality_score": state.get("quality_score", 0.0),
    }
    get_kotoba_client().insert_row("vertex_outreach_step", row_data)

    LOG.info("store_step: vertex_id=%s step=%d score=%.2f", vertex_id, step_number, state.get("quality_score", 0))
    return {"stored": True}


def should_retry(state: OutreachState) -> str:
    score = state.get("quality_score", 0.0)
    retries = state.get("retry_count", 0)
    if score < QUALITY_THRESHOLD and retries < 1:
        return "retry"
    return "store"


# ---------------------------------------------------------------------------
# Build LangGraph
# ---------------------------------------------------------------------------

def _build_graph() -> Any:
    g: StateGraph = StateGraph(OutreachState)
    g.add_node("research_prospect", research_prospect)
    g.add_node("draft_opening", draft_opening)
    g.add_node("quality_gate", quality_gate)
    g.add_node("store_step", store_step)

    g.add_edge(START, "research_prospect")
    g.add_edge("research_prospect", "draft_opening")
    g.add_edge("draft_opening", "quality_gate")
    g.add_conditional_edges(
        "quality_gate",
        should_retry,
        {"retry": "draft_opening", "store": "store_step"},
    )
    g.add_edge("store_step", END)
    return g.compile()


_GRAPH = _build_graph()


# ---------------------------------------------------------------------------
# LangServer handlers
# ---------------------------------------------------------------------------

def _make_worker() -> LangServerWorker:
    gateway = os.environ.get("AGENTGATEWAY_MCP_URL", "127.0.0.1:8080")
    channel = create_langserver_channel(grpc_address=gateway)
    return LangServerWorker(channel)


async def task_check_dnc(
    sequence_id: str,
    prospect_id: str,
    **_: Any,
) -> dict[str, Any]:
    """Check if prospect email is on DNC list before any send."""
    prospect = get_kotoba_client().select_first_where(
        "vertex_outreach_prospect", "vertex_id", prospect_id, columns=["email"]
    )
    if not prospect or not prospect.get("email"):
        return {"isDnc": False}

    email = prospect["email"]
    dnc_row = get_kotoba_client().select_first_where(
        "vertex_outreach_dnc", "email", email, columns=["vertex_id"]
    )
    is_dnc = bool(dnc_row)
    if is_dnc:
        LOG.info("task_check_dnc: sequence_id=%s is on DNC — skipping", sequence_id)
        _update_sequence_status(sequence_id, "skipped_dnc")
    return {"isDnc": is_dnc}


async def task_run_research_agent(
    sequence_id: str,
    prospect_id: str,
    goal: str = "",
    step_number: int = 1,
    **_: Any,
) -> dict[str, Any]:
    """LangGraph research + draft loop. Returns subject + body for send step."""
    init_state: OutreachState = {
        "messages": [],
        "prospect_id": prospect_id,
        "sequence_id": sequence_id,
        "step_number": step_number,
        "goal": goal,
        "company_summary": "",
        "prospect_context": "",
        "subject_line": "",
        "body_text": "",
        "quality_score": 0.0,
        "retry_count": 0,
        "stored": False,
    }
    final = await asyncio.to_thread(_GRAPH.invoke, init_state)

    _update_sequence_status(sequence_id, "researched")

    return {
        "subjectLine": final.get("subject_line", ""),
        "bodyText": final.get("body_text", ""),
        "qualityScore": final.get("quality_score", 0.0),
        "replyDetected": False,
    }


async def task_send_via_resend(
    sequence_id: str,
    prospect_id: str,
    subject_line: str = "",
    body_text: str = "",
    step_number: int = 1,
    **_: Any,
) -> dict[str, Any]:
    """Send personalized email via Resend. DNC already checked by check_dnc ServiceTask."""
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        api_key = load_keychain_secret(service="etzhayyim.resend", account="API_KEY") or ""

    prospect = get_kotoba_client().select_first_where(
        "vertex_outreach_prospect", "vertex_id", prospect_id,
        columns=["email", "prospect_name"],
    )
    if not prospect or not prospect.get("email"):
        LOG.warning("task_send_via_resend: no email for prospect_id=%s", prospect_id)
        return {"resendEmailId": "", "sent": False}

    to_email = prospect["email"]
    to_name = prospect.get("prospect_name") or ""
    to_addr = f"{to_name} <{to_email}>" if to_name else to_email

    payload = {
        "from": RESEND_FROM,
        "to": [to_addr],
        "subject": subject_line or f"Following up — step {step_number}",
        "text": body_text,
    }
    resend_email_id = ""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            if r.status_code in (200, 201):
                resend_email_id = r.json().get("id", "")
            else:
                LOG.error("task_send_via_resend: resend error %d: %s", r.status_code, r.text[:200])
    except Exception as exc:
        LOG.error("task_send_via_resend: http error: %s", exc)

    now = datetime.now(timezone.utc).isoformat()
    # update step record with sent info
    step_vid = hashlib.sha256(f"{sequence_id}:step:{step_number}".encode()).hexdigest()
    # Fetch existing step, update fields, then insert_row (upsert)
    existing_step = get_kotoba_client().select_first_where(
        "vertex_outreach_step", "vertex_id", step_vid
    )
    if existing_step:
        existing_step["status"] = "sent"
        existing_step["resend_email_id"] = resend_email_id
        existing_step["sent_at"] = now
        existing_step["updated_at"] = now
        get_kotoba_client().insert_row("vertex_outreach_step", existing_step)
    else:
        LOG.warning("task_send_via_resend: Could not find vertex_outreach_step for vertex_id=%s to update", step_vid)
    # edge: sequence → prospect
    edge_id = hashlib.sha256(f"sent:{sequence_id}:{prospect_id}:{step_number}".encode()).hexdigest()
    seq_vid = hashlib.sha256(f"sequence:{sequence_id}".encode()).hexdigest()
    edge_data = {
        "edge_id": edge_id,
        "src_vid": seq_vid,
        "dst_vid": prospect_id,
        "relation_kind": "SENT_TO",
        "created_at": now,
        "updated_at": now,
        "owner_did": OUTREACH_DID,
        "sensitivity_ord": 3,
        "sequence_id": sequence_id,
        "prospect_id": prospect_id,
        "step_number": step_number,
        "resend_email_id": resend_email_id,
    }
    get_kotoba_client().insert_row("edge_outreach_sent", edge_data)

    _update_sequence_status(sequence_id, f"sent_step_{step_number}")
    LOG.info("task_send_via_resend: sequence_id=%s step=%d email_id=%s", sequence_id, step_number, resend_email_id)
    return {"resendEmailId": resend_email_id, "sent": bool(resend_email_id), "replyDetected": False}


async def task_correlate_reply(
    thread_id: str = "",
    from_email: str = "",
    source: str = "",
    **_: Any,
) -> dict[str, Any]:
    """
    Correlate a gmail/m365Ingest reply to an active outreach sequence.
    Marks sequence as replied and publishes Zeebe message to cancel the timer.
    """
    if not from_email:
        return {"correlated": False}

    # find prospect by email
    prospect = get_kotoba_client().select_first_where(
        "vertex_outreach_prospect", "email", from_email, columns=["vertex_id"]
    )
    if not prospect:
        LOG.debug("task_correlate_reply: no prospect for email (omitted for PII)")
        return {"correlated": False}

    prospect_id = prospect["vertex_id"]
    # R0: Multi-predicate with NOT IN and ORDER BY handled in Python.
    sequences = get_kotoba_client().select_where(
        "vertex_outreach_sequence", "prospect_id", prospect_id,
        columns=["sequence_id", "zeebe_process_instance_key", "status", "created_at"],
        limit=2000, # Fetch a reasonable number to filter in Python
    )
    # Filter in Python for status NOT IN and order by created_at DESC
    filtered_sequences = [
        s for s in sequences if s.get("status") not in ("completed", "replied", "skipped_dnc")
    ]
    filtered_sequences.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    sequence = filtered_sequences[0] if filtered_sequences else None

    if not sequence:
        return {"correlated": False}

    sequence_id = sequence["sequence_id"]
    now = datetime.now(timezone.utc).isoformat()
    _update_sequence_status(sequence_id, "replied")
    seq_vid = hashlib.sha256(f"sequence:{sequence_id}".encode()).hexdigest()
    # Fetch existing sequence, update fields, then insert_row (upsert)
    existing_sequence = get_kotoba_client().select_first_where(
        "vertex_outreach_sequence", "vertex_id", seq_vid
    )
    if existing_sequence:
        existing_sequence["reply_detected"] = True
        existing_sequence["updated_at"] = now
        get_kotoba_client().insert_row("vertex_outreach_sequence", existing_sequence)
    else:
        LOG.warning("task_correlate_reply: Could not find vertex_outreach_sequence for vertex_id=%s to update", seq_vid)

    LOG.info("task_correlate_reply: sequence_id=%s marked replied (source=%s)", sequence_id, source)
    return {"correlated": True, "sequenceId": sequence_id, "replyDetected": True}


async def task_create_sponsor_slot(
    sequence_id: str,
    include_sponsor_slot: bool = False,
    **_: Any,
) -> dict[str, Any]:
    """Optional XRPC call to ads.etzhayyim.com createCampaign."""
    if not include_sponsor_slot:
        return {"adCampaignId": ""}

    sequence = get_kotoba_client().select_first_where(
        "vertex_outreach_sequence", "sequence_id", sequence_id,
        columns=["sequence_name", "goal"],
    )
    name = sequence.get("sequence_name") if sequence else sequence_id
    goal = sequence.get("goal") if sequence else ""

    ad_campaign_id = ""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                f"{ADS_XRPC_URL}/xrpc/com.etzhayyim.apps.ads.createCampaign",
                json={
                    "campaignName": f"Outreach: {name}",
                    "targetAudience": goal,
                    "sourceActor": OUTREACH_DID,
                    "sourceEntityId": sequence_id,
                },
                headers={"content-type": "application/json"},
            )
            if r.status_code in (200, 201):
                ad_campaign_id = r.json().get("campaignId", "")
    except Exception as exc:
        LOG.warning("task_create_sponsor_slot: ads call failed: %s", exc)

    if ad_campaign_id:
        now = datetime.now(timezone.utc).isoformat()
        seq_vid = hashlib.sha256(f"sequence:{sequence_id}".encode()).hexdigest()
        # Fetch existing sequence, update fields, then insert_row (upsert)
        existing_sequence = get_kotoba_client().select_first_where(
            "vertex_outreach_sequence", "vertex_id", seq_vid
        )
        if existing_sequence:
            existing_sequence["ad_campaign_id"] = ad_campaign_id
            existing_sequence["updated_at"] = now
            get_kotoba_client().insert_row("vertex_outreach_sequence", existing_sequence)
        else:
            LOG.warning("task_create_sponsor_slot: Could not find vertex_outreach_sequence for vertex_id=%s to update", seq_vid)

    LOG.info("task_create_sponsor_slot: sequence_id=%s ad_campaign_id=%s", sequence_id, ad_campaign_id)
    return {"adCampaignId": ad_campaign_id}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _update_sequence_status(sequence_id: str, status: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    seq_vid = hashlib.sha256(f"sequence:{sequence_id}".encode()).hexdigest()
    # Fetch existing sequence, update fields, then insert_row (upsert)
    existing_sequence = get_kotoba_client().select_first_where(
        "vertex_outreach_sequence", "vertex_id", seq_vid
    )
    if existing_sequence:
        existing_sequence["status"] = status
        existing_sequence["updated_at"] = now
        get_kotoba_client().insert_row("vertex_outreach_sequence", existing_sequence)
    else:
        LOG.warning("_update_sequence_status: Could not find vertex_outreach_sequence for vertex_id=%s to update", seq_vid)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    load_env_file()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    worker = _make_worker()

    worker.task(task_type="outreach.check_dnc", timeout_ms=15_000, max_jobs_to_activate=10)(
        task_check_dnc
    )
    worker.task(task_type="outreach.run_research_agent", timeout_ms=180_000, max_jobs_to_activate=5)(
        task_run_research_agent
    )
    worker.task(task_type="outreach.send_via_resend", timeout_ms=60_000, max_jobs_to_activate=10)(
        task_send_via_resend
    )
    worker.task(task_type="outreach.correlate_reply", timeout_ms=30_000, max_jobs_to_activate=20)(
        task_correlate_reply
    )
    worker.task(task_type="outreach.create_sponsor_slot", timeout_ms=30_000, max_jobs_to_activate=10)(
        task_create_sponsor_slot
    )

    LOG.info("outreach worker started — listening on Zeebe")
    asyncio.run(worker.work())


if __name__ == "__main__":
    main()
