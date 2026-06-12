"""
lawfirm.etzhayyim.com marketing LangGraph (BCI Rule 36-aware).

Architecture: Supervisor + 6 specialist agents + compliance gate + audit.

  START → supervisor →
    {content | social | outreach | platform | analytics | event}
       → compliance_gate (advocate-brand only) → emit_audit → END

Brand axis (CRITICAL):
  - "advocate" — k-bakshi personal practice. BCI Rule 36 strict: information-only,
    no soliciting, no testimonials, no success rate claims. Compliance gate REQUIRED.
  - "platform" — etzhayyim SaaS marketing. Commercial OK (NOT advocate practice
    advertising). Compliance gate skipped, but disclaimer-of-non-legal-advice required.

Persists: vertex_lawfirm_marketing_asset, vertex_lawfirm_marketing_run.

Registered as assistant_id="lawfirm-marketing-ops" in langgraph_server_app.

ADR-2605080600 LangGraph Server L3.
ADR-0036 Hyperdrive direct.
"""

from __future__ import annotations

import json
import logging
import time as _time
import uuid
from typing import Any, Literal, TypedDict
from kotodama.kotoba_datomic import get_kotoba_client

LOG = logging.getLogger("lawfirm.marketing")

_FIRM_DID  = "did:web:lawfirm.etzhayyim.com"
_OWNER_DID = "did:web:bpmn.etzhayyim.com"
_ETZ_DID   = "did:web:etz-hayim.etzhayyim.com"

# Compliance reviewer DIDs (CLO + COO authority for advocate-brand publish)
_COMPLIANCE_REVIEWERS = {
    "did:web:k-bakshi.etzhayyim.com",  # CLO + lead advocate (final say on BCI compliance)
    "did:web:a-nakamura.etzhayyim.com",  # COO (operational concur)
}

TaskKind = Literal[
    "content", "social", "outreach", "platform",
    "analytics", "event", "unknown",
]


# ── State ──────────────────────────────────────────────────────────────────────

class MarketingState(TypedDict, total=False):
    # Input
    task_type: str
    brand: str
    audience: str
    topic: str
    payload: str
    schedule_at: str
    requester_did: str
    thread_id: str

    # Supervisor
    kind: TaskKind
    routing_reason: str

    # Specialist
    asset_kind: str
    title: str
    body_md: str
    target_url: str
    asset_uris: list[str]

    # Compliance
    compliance_check: str
    compliance_notes: str
    compliance_score: float

    # Lifecycle
    summary: str
    ok: bool
    error: str | None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    import datetime as _dt
    return _dt.datetime.now(tz=_dt.UTC).strftime("%Y-%m-%d %H:%M:%S")

def _vid(kind: str) -> str:
    import datetime as _dt
    stamp = _dt.datetime.now(tz=_dt.UTC).strftime("%Y%m%d%H%M%S")
    return f"at://{_OWNER_DID}/com.etzhayyim.apps.lawfirm.{kind}/{stamp}-{uuid.uuid4().hex[:8]}"


def _llm_md(system: str, user: str, max_tokens: int = 1800) -> str:
    """Call LLM and return raw markdown body."""
    try:
        from kotodama.llm import call_tier
        result = call_tier("balanced", system=system, user=user, max_tokens=max_tokens)
        return str(result.get("content", "")).strip()
    except Exception as exc:
        LOG.warning("LLM markdown call failed: %s", exc)
        return ""


def _llm_json(system: str, user: str, max_tokens: int = 800) -> dict:
    try:
        from kotodama.llm import call_tier
        result = call_tier("structured", system=system, user=user, max_tokens=max_tokens)
        content = result.get("content", "")
        if "```" in content:
            for chunk in content.split("```")[1::2]:
                stripped = chunk.lstrip("json").strip()
                try:
                    return json.loads(stripped)
                except Exception:
                    pass
        try:
            return json.loads(content)
        except Exception:
            return {"raw": content}
    except Exception as exc:
        LOG.warning("LLM JSON call failed: %s", exc)
        return {"error": str(exc)}


def _db_insert(table: str, row: dict) -> bool:
    try:
        get_kotoba_client().insert_row(table, row)
        return True
    except Exception as exc:
        LOG.warning("DB insert %s failed: %s", table, exc)
        return False


def _db_query(sql_str: str, params: dict | None = None) -> list[dict]:
    try:
        # R0: This is a direct SQL string, needs to be converted to Datalog if possible.
        # For now, it's passed as a raw query to kotoba_datomic's q() for compatibility.
        # This might not be optimal and could be further optimized with select_where.
        # However, the original query implies joins or more complex filtering.
        return get_kotoba_client().q(sql_str, args=params.values() if params else ())
    except Exception as exc:
        LOG.warning("DB query failed: %s", exc)
        return []


def _envelope_content(state: MarketingState, envelope_key: str) -> str:
    """Phase E3: extract content from `<envelope_key>.result.content` set by
    the upstream `mcp://com.etzhayyim.tools.llm.chat` node. Returns '' if absent.
    Mirrors webmk_proposal:_envelope_content."""
    envelope = state.get(envelope_key)  # type: ignore[arg-type]
    if isinstance(envelope, dict):
        result = envelope.get("result")
        if isinstance(result, dict):
            content = result.get("content")
            if isinstance(content, str) and content:
                return content
    return ""


# Per-domain envelope keys (mcp_tool result_key) and asset metadata.
_DOMAIN_ENVELOPE: dict[str, tuple[str, str]] = {
    # kind → (envelope_key, asset_kind)
    "content":  ("contentLlmOut",  "blog_article"),
    "social":   ("socialLlmOut",   "linkedin_post"),
    "outreach": ("outreachLlmOut", "outreach_mail"),
    "platform": ("platformLlmOut", "platform_copy"),
    "event":    ("eventLlmOut",    "event_brief"),
}


def _resolve_asset_from_envelope(state: MarketingState) -> tuple[str, str, str]:
    """Return (asset_kind, title, body_md) sourced from the per-kind LLM
    envelope when state has not been populated by a legacy py_primitive
    domain agent. Falls back to existing state fields."""
    body_md = state.get("body_md", "") or ""
    asset_kind = state.get("asset_kind", "") or ""
    title = state.get("title", "") or ""
    if body_md and asset_kind and title:
        return asset_kind, title, body_md
    kind = state.get("kind") or ""
    pair = _DOMAIN_ENVELOPE.get(kind)
    if pair is None:
        return asset_kind, title, body_md
    envelope_key, default_asset_kind = pair
    if not body_md:
        body_md = _envelope_content(state, envelope_key)
    if not asset_kind:
        asset_kind = default_asset_kind
    if not title:
        topic = state.get("topic") or state.get("task_type", "")
        if kind == "outreach":
            audience = state.get("audience", "")
            title = f"Outreach to {audience or 'firm'}"[:120]
        elif kind == "platform":
            title = f"Platform: {topic}"[:160]
        elif kind == "event":
            title = f"Event: {topic}"[:160]
        elif topic:
            title = (topic.split(":")[-1] if ":" in topic else topic).strip()
            if kind == "social":
                title = title[:120]
            else:
                title = title[:200]
        else:
            title = "Insight"
    return asset_kind, title, body_md


# ── Node: supervisor ───────────────────────────────────────────────────────────

_PREFIX_MAP: dict[str, TaskKind] = {
    "marketing.blogDraft":       "content",
    "marketing.articleDraft":    "content",
    "marketing.linkedinPost":    "social",
    "marketing.podcastBrief":    "social",
    "marketing.outreachMail":    "outreach",
    "marketing.peerFirmIntro":   "outreach",
    "marketing.platformCopy":    "platform",
    "marketing.demoDeck":        "platform",
    "marketing.kpiReport":       "analytics",
    "marketing.eventPrep":       "event",
    "marketing.complianceCheck": "content",  # routes to content+gate only
}


def supervisor(state: MarketingState) -> dict:
    task_type = state.get("task_type", "")
    for prefix, kind in _PREFIX_MAP.items():
        if task_type.startswith(prefix):
            return {"kind": kind, "routing_reason": f"prefix match: {prefix}"}

    # Fallback: keyword-based routing
    t_lower = task_type.lower()
    if any(k in t_lower for k in ("blog", "article", "post.long")):
        return {"kind": "content", "routing_reason": "keyword fallback: content"}
    if any(k in t_lower for k in ("linkedin", "twitter", "social")):
        return {"kind": "social", "routing_reason": "keyword fallback: social"}
    if any(k in t_lower for k in ("mail", "outreach", "intro")):
        return {"kind": "outreach", "routing_reason": "keyword fallback: outreach"}
    if any(k in t_lower for k in ("platform", "saas", "demo")):
        return {"kind": "platform", "routing_reason": "keyword fallback: platform"}
    if "kpi" in t_lower or "report" in t_lower:
        return {"kind": "analytics", "routing_reason": "keyword fallback: analytics"}
    if "event" in t_lower or "conference" in t_lower:
        return {"kind": "event", "routing_reason": "keyword fallback: event"}
    return {"kind": "unknown", "routing_reason": "no match"}


# ── Node: content_agent (blog/article) ─────────────────────────────────────────

_CONTENT_SYSTEM = """You are the content agent for lawfirm.etzhayyim.com.
Brand: ADVOCATE (k-bakshi personal practice) means BCI Rule 36 strict —
information-only, no soliciting, no success rate claims, no testimonials.

Draft an EDUCATIONAL blog article in English on the given topic.
Audience: typically NRI / Indian SMB / Japan-India cross-border tech firms.

Requirements:
- 800-1500 words markdown
- Clear H2/H3 structure
- Cite Indian statute / case law where relevant
- Include "Disclaimer: This article is for general information only and does
  not constitute legal advice. Consult a qualified advocate for specific matters."
  at the bottom

Output ONLY the article body in markdown, NO meta commentary.
"""

def content_agent(state: MarketingState) -> dict:
    topic = state.get("topic") or state.get("task_type", "")
    audience = state.get("audience", "general")
    payload = state.get("payload", "")
    user_msg = (
        f"Topic: {topic}\nAudience: {audience}\n"
        f"Reference context: {payload[:2000]}"
    )
    body = _llm_md(_CONTENT_SYSTEM, user_msg, max_tokens=2400)
    title = topic.split(":")[-1].strip() if topic else "Insight"
    return {
        "asset_kind": "blog_article",
        "title": title[:200],
        "body_md": body,
        "ok": bool(body),
    }


# ── Node: social_agent (LinkedIn) ──────────────────────────────────────────────

_SOCIAL_SYSTEM = """You are the social agent for lawfirm.etzhayyim.com (advocate brand).
Draft a LinkedIn post (k-bakshi personal account) on the given topic.

Requirements:
- 150-400 words, plain text (no markdown)
- Educational / observational tone
- ZERO solicitation language ("hire me", "contact for representation" forbidden)
- Optional 2-4 hashtags at the end
- May include link to the lawfirm.etzhayyim.com/insights blog if relevant
- Sign off as "— Kunal"
"""

def social_agent(state: MarketingState) -> dict:
    topic = state.get("topic") or state.get("task_type", "")
    audience = state.get("audience", "Indian legal tech community")
    payload = state.get("payload", "")
    user_msg = f"Topic: {topic}\nAudience: {audience}\nContext: {payload[:1500]}"
    body = _llm_md(_SOCIAL_SYSTEM, user_msg, max_tokens=700)
    title = (topic.split(":")[-1] if topic else "Linkedin post").strip()
    return {
        "asset_kind": "linkedin_post",
        "title": title[:120],
        "body_md": body,
        "ok": bool(body),
    }


# ── Node: outreach_agent (peer firm intro mail) ───────────────────────────────

_OUTREACH_SYSTEM = """You are the outreach agent. Draft a warm-intro email for
k-bakshi to send to a mid-tier Indian law firm partner.

This is NOT a cold sales mail — it's a peer introduction with two angles:
(1) Bakshi & Partners LLP (incorporation in progress) for referral collaboration,
(2) lawfirm.etzhayyim.com SaaS pilot (3-month no-cost) — ONLY mention if asked.

Requirements:
- 200-350 words
- English, professional, warm
- ZERO BCI Rule 36 violation: never claim success rates, never compare to
  other firms negatively, never use "best/leading/top" superlatives
- End with "Best, Kunal Bakshi" + role line
- Include a clear ask (30 min meeting, Bangalore in-person preferred)
"""

def outreach_agent(state: MarketingState) -> dict:
    audience = state.get("audience", "")
    topic = state.get("topic", "")
    payload = state.get("payload", "")
    user_msg = (
        f"Target firm + partner: {audience}\n"
        f"Specific angle / their practice: {topic}\n"
        f"Reference context: {payload[:1500]}"
    )
    body = _llm_md(_OUTREACH_SYSTEM, user_msg, max_tokens=900)
    title = f"Outreach to {audience or 'firm'}"
    return {
        "asset_kind": "outreach_mail",
        "title": title[:120],
        "body_md": body,
        "ok": bool(body),
    }


# ── Node: platform_agent (etzhayyim SaaS marketing) ───────────────────────────

_PLATFORM_SYSTEM = """You are the platform marketing agent for lawfirm.etzhayyim.com
SaaS, operated by etzhayyim. Brand = PLATFORM, NOT advocate practice.
Commercial marketing copy is OK (this is a tech operator product page, not
advocate solicitation).

Draft the requested platform marketing copy.

Requirements:
- Match the asset_kind in task_type (landing-page section / tweet / one-pager).
- Word count: tweet 220 chars / landing section 200-400 words / one-pager 600-900 words
- Highlight differentiation: multilingual intake, cross-border auto-route,
  BCI Rule 36 + DPDP Act 2023-grade encryption, BPMN audit trail
- Include "etzhayyim is a platform operator. lawfirm.etzhayyim.com SaaS does not
  provide legal advice; the customer firm's advocates retain all
  professional responsibility." disclaimer at the bottom
- ZERO advocate-practice language (no "we represent clients", etc.)
"""

def platform_agent(state: MarketingState) -> dict:
    topic = state.get("topic") or state.get("task_type", "")
    audience = state.get("audience", "mid-tier Indian law firm decision maker")
    payload = state.get("payload", "")
    user_msg = f"Asset type: {topic}\nAudience: {audience}\nContext: {payload[:1500]}"
    body = _llm_md(_PLATFORM_SYSTEM, user_msg, max_tokens=1500)
    title = f"Platform: {topic}"
    return {
        "asset_kind": "platform_copy",
        "title": title[:160],
        "body_md": body,
        "ok": bool(body),
    }


# ── Node: analytics_agent (KPI summary from RW MVs) ───────────────────────────

def analytics_agent(state: MarketingState) -> dict:
    """Pull KPI snapshot from streaming MVs and synthesize a brief."""
    revenue = _db_query(
        "SELECT month, currency, stream, amount_minor_total, payment_count "
        "FROM mv_lawfirm_revenue_monthly ORDER BY month DESC LIMIT 6"
    )
    outstanding = _db_query(
        "SELECT COUNT(*) AS cnt, SUM(total_minor) AS total_minor "
        "FROM mv_lawfirm_outstanding_invoices"
    )
    publish = _db_query(
        "SELECT compliance_check, COUNT(*) AS cnt "
        "FROM mv_lawfirm_marketing_publish_calendar GROUP BY compliance_check"
    )
    snapshot = {
        "revenue_last_6mo": revenue,
        "outstanding":      (outstanding[0] if outstanding else {}),
        "marketing_pipeline": publish,
    }

    summary_md = _llm_md(
        "You are a CFO/CRO assistant. Given the KPI snapshot, write a 1-page "
        "executive markdown summary in Japanese (重要メトリクス、トレンド、3 アクション). "
        "Be specific and numeric. NO speculation beyond the data.",
        json.dumps(snapshot, ensure_ascii=False, default=str)[:4000],
        max_tokens=1200,
    )
    return {
        "asset_kind": "kpi_report",
        "title": f"KPI Snapshot {_now_iso()[:10]}",
        "body_md": summary_md or json.dumps(snapshot, ensure_ascii=False, default=str)[:2000],
        "ok": True,
    }


# ── Node: event_agent (conference / meetup prep brief) ────────────────────────

_EVENT_SYSTEM = """You are the event prep agent. Draft a 1-page briefing for
k-bakshi attending a conference / meetup / podcast.

Include:
- Talking points (3-5 bullet, BCI Rule 36-safe)
- 2-3 questions to ask other speakers
- 5 target conversations (audience profile + opening line)
- Reciprocal value (what we offer in conversations)
- Disclaimer of advocate practice (do not solicit during the event)

Output markdown.
"""

def event_agent(state: MarketingState) -> dict:
    topic = state.get("topic") or "Indian Legal Tech Summit"
    payload = state.get("payload", "")
    user_msg = f"Event: {topic}\nContext: {payload[:1500]}"
    body = _llm_md(_EVENT_SYSTEM, user_msg, max_tokens=1500)
    return {
        "asset_kind": "event_brief",
        "title": f"Event: {topic}"[:160],
        "body_md": body,
        "ok": bool(body),
    }


# ── Node: compliance_gate ─────────────────────────────────────────────────────

_COMPLIANCE_SYSTEM = """You are the BCI Rule 36 compliance reviewer for
lawfirm.etzhayyim.com advocate-brand marketing.

CHECK the draft for these violations (any => REJECTED):
- Direct solicitation ("hire me", "engage me", "contact for representation")
- Success rate claims ("95% win rate", "settled 100s of cases")
- Comparison superlatives ("best lawyer", "leading", "top-rated")
- Testimonials / client quotes
- Promises of outcome
- Negative comparison to other lawyers
- Missing legal-advice disclaimer (in 800+ word articles)

CHECK these soft warnings (=> NEEDS_REVIEW):
- Borderline self-promotion language
- Vague achievement claims without source
- First-person legal opinion stated as universal truth

OUTPUT JSON: {
  "compliance_check": "approved" | "rejected" | "needs_review",
  "compliance_score": 0.0-1.0 (1.0 = perfect),
  "compliance_notes": "<violations or notes, Japanese OK>"
}
"""

def compliance_gate(state: MarketingState) -> dict:
    brand = state.get("brand", "advocate")
    # Phase E3: source body_md from upstream mcp_tool envelope when v2
    # `<domain>_call_llm` is the upstream node; fall back to state field.
    asset_kind, _title, body = _resolve_asset_from_envelope(state)
    _ = asset_kind  # noqa: F841 — emit_audit reuses the same resolver

    # Platform brand → skip strict gate, just disclaimer check
    if brand == "platform":
        if "platform operator" not in body.lower() and "does not provide legal advice" not in body.lower():
            return {
                "compliance_check": "needs_review",
                "compliance_notes": "Platform copy missing required non-legal-advice disclaimer.",
                "compliance_score": 0.6,
            }
        return {
            "compliance_check": "approved",
            "compliance_notes": "Platform brand: disclaimer present, commercial copy permitted.",
            "compliance_score": 0.95,
        }

    if not body:
        return {
            "compliance_check": "rejected",
            "compliance_notes": "Empty body; LLM produced no draft.",
            "compliance_score": 0.0,
        }

    user_msg = f"Asset kind: {state.get('asset_kind')}\nDraft body:\n{body[:5000]}"
    result = _llm_json(_COMPLIANCE_SYSTEM, user_msg, max_tokens=600)
    return {
        "compliance_check": str(result.get("compliance_check") or "needs_review"),
        "compliance_notes": str(result.get("compliance_notes") or ""),
        "compliance_score": float(result.get("compliance_score") or 0.5),
    }


# ── Node: emit_audit + persist asset ──────────────────────────────────────────

def emit_audit(state: MarketingState) -> dict:
    """Persist the drafted asset + run log."""
    # Phase E3: source asset_kind/title/body_md from the upstream mcp_tool
    # envelope when v2 `<domain>_call_llm` ran upstream; fall back to state.
    asset_kind, title, body = _resolve_asset_from_envelope(state)
    if not asset_kind:
        asset_kind = "unknown"
    brand      = state.get("brand", "advocate")
    compliance = state.get("compliance_check", "skipped")
    notes      = state.get("compliance_notes", "")
    score      = state.get("compliance_score", 0.0)
    schedule   = state.get("schedule_at", "")

    asset_vid = _vid("marketingAsset")
    _db_insert("vertex_lawfirm_marketing_asset", {
        "vertex_id":        asset_vid,
        "asset_kind":       asset_kind,
        "brand":            brand,
        "audience":         state.get("audience", ""),
        "title":            title,
        "body_md":          body[:60_000],
        "target_url":       state.get("target_url", ""),
        "compliance_check": compliance,
        "compliance_notes": notes[:2000],
        "compliance_score": score,
        "reviewer_did":     "did:web:lawfirm.etzhayyim.com",
        "scheduled_at":     schedule,
        "published_at":     "",
        "published_url":    "",
        "llm_model":        "balanced+structured",
        "created_at":       _now_iso(),
        "owner_did":        _FIRM_DID,
    })

    run_vid = _vid("marketingRun")
    ts_ms = int(_time.time() * 1000)
    _db_insert("vertex_lawfirm_marketing_run", {
        "vertex_id":      run_vid,
        "run_id":         f"mkt-{ts_ms}",
        "task_type":      state.get("task_type", ""),
        "brand":          brand,
        "requester_did":  state.get("requester_did", ""),
        "result_summary": (title + " :: " + compliance)[:500],
        "asset_count":    1 if body else 0,
        "ok":             state.get("ok", True),
        "error":          state.get("error") or "",
        "started_at":     _now_iso(),
        "finished_at":    _now_iso(),
        "created_at":     _now_iso(),
        "owner_did":      _FIRM_DID,
    })

    return {
        "asset_uris": [asset_vid],
        "summary":    (title + " (" + compliance + ", score=" + f"{score:.2f}" + ")")[:500],
    }


# ── Routers ────────────────────────────────────────────────────────────────────

def _route_kind(state: MarketingState) -> str:
    return state.get("kind") or "unknown"


# ── Graph factory ──────────────────────────────────────────────────────────────

def build_graph():
    """
    Compile the lawfirm marketing StateGraph.

    Flow:
      supervisor → (kind router) →
        {content | social | outreach | platform | analytics | event}
          → compliance_gate → emit_audit → END
    """
    from langgraph.graph import END, StateGraph

    builder = StateGraph(MarketingState)

    builder.add_node("supervisor",       supervisor)
    builder.add_node("content",          content_agent)
    builder.add_node("social",           social_agent)
    builder.add_node("outreach",         outreach_agent)
    builder.add_node("platform",         platform_agent)
    builder.add_node("analytics",        analytics_agent)
    builder.add_node("event",            event_agent)
    builder.add_node("compliance_gate",  compliance_gate)
    builder.add_node("emit_audit",       emit_audit)

    builder.set_entry_point("supervisor")

    builder.add_conditional_edges(
        "supervisor",
        _route_kind,
        {
            "content":   "content",
            "social":    "social",
            "outreach":  "outreach",
            "platform":  "platform",
            "analytics": "analytics",
            "event":     "event",
            "unknown":   "content",
        },
    )

    for node in ("content", "social", "outreach", "platform", "analytics", "event"):
        builder.add_edge(node, "compliance_gate")
    builder.add_edge("compliance_gate", "emit_audit")
    builder.add_edge("emit_audit", END)

    return builder.compile()
