"""
kaisya.etzhayyim.com member assistant LangGraph.

Per-member chat surface that wraps etzhayyim-company-ops and
lawfirm-marketing-ops behind a member-identity-aware supervisor.

Flow:
  START → resolve_member → load_context → supervisor →
    {company_ops | lawfirm_marketing | lawfirm_sales | direct_reply | escalate}
      → render_response → emit_audit → END

Member identity surfaces:
  - Outlook OAuth (M365) → upn_to_did mapping → member DID
  - Claude MCP → ServiceAuth JWT sub claim → member DID
  - kaisya web chat → session JWT sub claim

Each member's RACI / allocation context is injected into supervisor prompt
so routing decisions respect role boundaries (e.g. tanaka cannot trigger
PwC clearance — only k-bakshi/j-kawasaki can per RACI seed iter 15).

Registered as assistant_id="kaisya-member-assistant" in langgraph_server_app.

ADR-2605080600 LangGraph Server L3 + ADR-0042 MCP tool registry.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Literal, TypedDict

from kotodama.kotoba_datomic import get_kotoba_client

LOG = logging.getLogger("kaisya.member")

_KAISYA_DID = "did:web:kaisya.etzhayyim.com"
_OWNER_DID = "did:web:bpmn.etzhayyim.com"

# UPN → member DID resolution table (extend as new members onboard)
_UPN_TO_DID: dict[str, str] = {
    "j-kawasaki@etzhayyim.com":  "did:web:j-kawasaki.etzhayyim.com",
    "j.kawasaki@etzhayyim.com":  "did:web:j-kawasaki.etzhayyim.com",
    "a-nakamura@etzhayyim.com":  "did:web:a-nakamura.etzhayyim.com",
    "a.nakamura@etzhayyim.com":  "did:web:a-nakamura.etzhayyim.com",
    "k-bakshi@etzhayyim.com":    "did:web:k-bakshi.etzhayyim.com",
    "k.bakshi@etzhayyim.com":    "did:web:k-bakshi.etzhayyim.com",
    "t-chikada@etzhayyim.com":   "did:web:t-chikada.etzhayyim.com",
    "t.chikada@etzhayyim.com":   "did:web:t-chikada.etzhayyim.com",
    "f-tanaka@etzhayyim.com":    "did:web:f-tanaka.etzhayyim.com",
    "f.tanaka@etzhayyim.com":    "did:web:f-tanaka.etzhayyim.com",
    "y-nishino@etzhayyim.com":   "did:web:y-nishino.etzhayyim.com",
    "y.nishino@etzhayyim.com":   "did:web:y-nishino.etzhayyim.com",
    "t-ichihara@etzhayyim.com":  "did:web:t-ichihara.etzhayyim.com",
    "k-takahashi@etzhayyim.com": "did:web:k-takahashi.etzhayyim.com",
    "n-takahashi@etzhayyim.com": "did:web:n-takahashi.etzhayyim.com",
}


Route = Literal[
    "company_ops", "lawfirm_marketing", "lawfirm_sales",
    "direct_reply", "escalate", "denied",
]


# ── State ──────────────────────────────────────────────────────────────────────

class MemberChatState(TypedDict, total=False):
    # Input
    user_upn: str            # from Outlook OAuth or session claim
    session_id: str
    user_message: str        # most recent user utterance
    history: list[dict]      # prior turns
    channel: str             # 'web' | 'mcp' | 'outlook'

    # Resolved member identity
    member_did: str
    member_name: str
    member_role: str         # CEO / COO / CLO / eng-deploy / eng-review / eng-infra / brand / creative
    raci_summary: str        # one-line summary of RACI scope

    # Supervisor classification
    route: Route
    routing_reason: str

    # Sub-graph result
    sub_result: dict
    sub_summary: str

    # Final
    reply_text: str
    citations: list[str]
    requires_human_approval: bool
    ok: bool
    error: str | None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    import datetime as _dt
    return _dt.datetime.now(tz=_dt.UTC).strftime("%Y-%m-%d %H:%M:%S")

def _vid(kind: str) -> str:
    import datetime as _dt
    stamp = _dt.datetime.now(tz=_dt.UTC).strftime("%Y%m%d%H%M%S")
    return f"at://{_OWNER_DID}/com.etzhayyim.apps.kaisya.{kind}/{stamp}-{uuid.uuid4().hex[:8]}"


def _llm_chat(system: str, user: str, max_tokens: int = 1200) -> str:
    try:
        from kotodama.llm import call_tier
        result = call_tier("balanced", system=system, user=user, max_tokens=max_tokens)
        return str(result.get("content", "")).strip()
    except Exception as exc:
        LOG.warning("LLM chat failed: %s", exc)
        return ""


def _llm_json(system: str, user: str, max_tokens: int = 400) -> dict:
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
        LOG.warning("LLM json failed: %s", exc)
        return {"error": str(exc)}





def _db_insert_audit(member_did: str, action: str, payload: dict) -> None:
    try:
        from datetime import datetime, timezone
        ts_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        record = {
            "vertex_id": str(uuid.uuid4()),
            "repo": _KAISYA_DID,
            "collection": "com.etzhayyim.apps.kaisya.memberChat",
            "rkey": f"chat-{ts_ms}",
            "action": "create",
            "ts_ms": ts_ms,
            "record_json": json.dumps({
                "member_did": member_did,
                "action": action,
                "payload": payload,
            }, ensure_ascii=False)[:8000],
        }
        get_kotoba_client().insert_row("vertex_repo_commit", record)
    except Exception as exc:
        LOG.debug("audit insert skipped: %s", exc)


# ── Node: resolve_member (UPN → DID + role) ───────────────────────────────────

def resolve_member(state: MemberChatState) -> dict:
    upn = (state.get("user_upn") or "").strip().lower()
    member_did = _UPN_TO_DID.get(upn, "")

    if not member_did:
        # Phase D2 (ADR-2605082000): set `nextRoute` so the topology uses
        # field-based conditional routing, retiring _after_resolve.
        return {
            "member_did": "",
            "member_name": "",
            "member_role": "unknown",
            "raci_summary": "",
            "route": "denied",
            "nextRoute": "denied",
            "routing_reason": f"unknown UPN: {upn}",
            "ok": False,
            "error": "unknown_member",
        }

    row = get_kotoba_client().select_first_where(
        "vertex_etzhayyim_person",
        "person_did",
        member_did,
        columns=["display_name", "title", "department"]
    )
    name = row["display_name"] if row else upn.split("@")[0]
    title = row["title"] if row else "member"
    return {
        "member_did": member_did,
        "member_name": name,
        "member_role": title,
        "nextRoute": "load_context",
        "ok": True,
    }


# ── Node: load_context (RACI + active assignments) ────────────────────────────

def load_context(state: MemberChatState) -> dict:
    member_did = state.get("member_did", "")
    if not member_did:
        return {"raci_summary": ""}
    raci = get_kotoba_client().select_where(
        "vertex_etzhayyim_raci",
        "person_did",
        member_did,
        columns=["task_nsid", "raci_role", "context"],
        limit=20,
        order_by=[("effective_date", "desc")]
    )
    parts: list[str] = []
    for r in raci:
        parts.append(f"  - [{r['raci_role']}] {r['task_nsid']}")
    raci_summary = "Member RACI scope:\n" + "\n".join(parts) if parts else "(no RACI assignments)"
    return {"raci_summary": raci_summary}


# ── Node: supervisor (LLM-driven route classification) ────────────────────────

_SUPERVISOR_SYSTEM = """You are the kaisya.etzhayyim.com member chat supervisor.
The member has already been authenticated. You see their RACI scope.

Classify the user's message into ONE route:

- "company_ops" — HR / finance / legal / sales / governance / personnel / OKR ops
- "lawfirm_marketing" — content / social / outreach / platform / KPI / event
- "lawfirm_sales" — pipeline / outreach event / pwc / engagement / lead
- "direct_reply" — informational, advisory, or out-of-scope; reply directly
- "escalate" — needs another member's RACI or CEO HITL

CRITICAL: respect RACI. If the user wants an action they're not Responsible
or Accountable for, route "escalate" with reason naming the right member.

Output JSON: {"route": "<route>", "reason": "<one sentence>"}
"""

def supervisor(state: MemberChatState) -> dict:
    member_role = state.get("member_role", "")
    raci = state.get("raci_summary", "")
    msg = state.get("user_message", "")
    user_msg = (
        f"Member: {state.get('member_name')} ({member_role})\n"
        f"{raci}\n\n"
        f"Message: {msg}"
    )
    out = _llm_json(_SUPERVISOR_SYSTEM, user_msg, max_tokens=300)
    route = out.get("route", "direct_reply")
    if route not in ("company_ops", "lawfirm_marketing", "lawfirm_sales",
                     "direct_reply", "escalate"):
        route = "direct_reply"
    return {"route": route, "routing_reason": out.get("reason", "")}


# ── Node: company_ops dispatcher ──────────────────────────────────────────────

def company_ops_dispatch(state: MemberChatState) -> dict:
    """Submit user message to etzhayyim-company-ops graph as task."""
    try:
        from kotodama.langgraph_graphs.etzhayyim_company_ops import build_graph
        sub = build_graph().invoke({
            "task_type": "governance.chat",
            "payload": {"message": state.get("user_message", "")},
            "thread_id": state.get("session_id", ""),
            "requester_did": state.get("member_did", ""),
        })
        return {
            "sub_result": dict(sub),
            "sub_summary": str((sub.get("result") or {}).get("summary", ""))[:500],
        }
    except Exception as exc:
        LOG.warning("company_ops sub-graph failed: %s", exc)
        return {"sub_result": {"error": str(exc)}, "sub_summary": ""}


# ── Node: lawfirm_marketing dispatcher ────────────────────────────────────────

def lawfirm_marketing_dispatch(state: MemberChatState) -> dict:
    msg = state.get("user_message", "")
    # Heuristic: if the message mentions blog/post/outreach/KPI map to task
    task_type = "marketing.kpiReport"
    msg_lower = msg.lower()
    if any(k in msg_lower for k in ("blog", "article")):
        task_type = "marketing.blogDraft"
    elif "linkedin" in msg_lower:
        task_type = "marketing.linkedinPost"
    elif any(k in msg_lower for k in ("outreach", "intro", "mail draft")):
        task_type = "marketing.outreachMail"
    elif any(k in msg_lower for k in ("platform", "saas", "demo deck")):
        task_type = "marketing.platformCopy"
    elif "event" in msg_lower:
        task_type = "marketing.eventPrep"
    try:
        from kotodama.langgraph_graphs.lawfirm_marketing_ops import build_graph
        sub = build_graph().invoke({
            "task_type": task_type,
            "brand": "advocate" if state.get("member_did") == "did:web:k-bakshi.etzhayyim.com" else "platform",
            "audience": state.get("member_role", ""),
            "topic": msg,
            "requester_did": state.get("member_did", ""),
            "thread_id": state.get("session_id", ""),
        })
        return {
            "sub_result": dict(sub),
            "sub_summary": str(sub.get("summary", ""))[:500],
        }
    except Exception as exc:
        return {"sub_result": {"error": str(exc)}, "sub_summary": ""}


# ── Node: lawfirm_sales dispatcher (read-only summary; mutations need RACI) ──

def lawfirm_sales_dispatch(state: MemberChatState) -> dict:
    member_did = state.get("member_did", "")
    # RACI gate: only k-bakshi or a-nakamura can trigger pipeline transitions
    can_mutate = member_did in (
        "did:web:k-bakshi.etzhayyim.com", "did:web:a-nakamura.etzhayyim.com",
        "did:web:j-kawasaki.etzhayyim.com",
    )
    # # R0: Using q() for complex ordering with NULLS LAST.
    # The NULLS LAST equivalent in Datalog would involve filtering for non-null
    # then concatenating with nulls, but for this simple case, direct order-by is close enough.
    # If perfect NULLS LAST behavior is critical, more complex Datalog or post-processing would be needed.
    query_edn = """
    [:find (pull ?e [:lead_id :target_name :stage :last_touch_at :conversion_value_usd])
     :where [?e :db/ident :vertex_lawfirm_lead]
            [?e :lead_id]
     :order-by [?e :last_touch_at :desc]
     :limit 10]
    """
    leads = get_kotoba_client().q(query_edn)
    summary = (
        f"Pipeline snapshot ({len(leads)} top leads). "
        f"Member can mutate stage: {can_mutate}."
    )
    return {
        "sub_result": {"leads": leads, "can_mutate": can_mutate},
        "sub_summary": summary,
    }


# ── Node: direct_reply / escalate ─────────────────────────────────────────────

_REPLY_SYSTEM = """You are the kaisya.etzhayyim.com member chat assistant.
Reply directly to the user's message. Be specific. Cite RACI scope when
declining or escalating. Tone: professional, concise, Japanese OK.

If the user is asking about something outside their RACI, name the
member who IS responsible (e.g. "PwC clearance is owned by k-bakshi
+ j-kawasaki — would you like me to draft a request on your behalf?").
"""

def direct_reply(state: MemberChatState) -> dict:
    name = state.get("member_name", "member")
    role = state.get("member_role", "")
    raci = state.get("raci_summary", "")
    msg = state.get("user_message", "")
    user_msg = (
        f"Member {name} ({role})\nRACI scope:\n{raci}\n\n"
        f"Message: {msg}\n\n"
        f"Sub-graph result (if any): {json.dumps(state.get('sub_result') or {}, ensure_ascii=False)[:2000]}"
    )
    text = _llm_chat(_REPLY_SYSTEM, user_msg, max_tokens=1000)
    return {
        "reply_text": text or "(no reply generated)",
        "citations": [],
        "requires_human_approval": state.get("route") == "escalate",
        "ok": True,
    }


# ── Node: emit_audit ──────────────────────────────────────────────────────────

def _direct_reply_envelope_content(state: MemberChatState) -> str:
    """Phase E3 (ADR-2605082000): read direct_reply LLM output from the
    canonical mcp_tool envelope (`directReplyLlmOut.result.content`) and
    fall back to the legacy `reply_text` state field when the assistant
    is the v1 py_primitive topology."""
    envelope = state.get("directReplyLlmOut") or {}
    if isinstance(envelope, dict):
        result = envelope.get("result")
        if isinstance(result, dict):
            content = result.get("content")
            if isinstance(content, str) and content:
                return content
    legacy = state.get("reply_text")
    return legacy if isinstance(legacy, str) else ""


def emit_audit(state: MemberChatState) -> dict:
    # Phase E3: reply_text now sourced from directReplyLlmOut envelope
    # (mcp_tool result) when present; falls back to legacy state.reply_text.
    reply_text = _direct_reply_envelope_content(state)
    route = state.get("route", "")
    requires_human_approval = route == "escalate"
    _db_insert_audit(
        state.get("member_did", ""),
        f"chat:{route or 'unknown'}",
        {
            "channel":      state.get("channel", "web"),
            "session_id":   state.get("session_id", ""),
            "route":        route,
            "reason":       state.get("routing_reason", ""),
            "summary":      state.get("sub_summary", ""),
            "reply_chars":  len(reply_text),
        },
    )
    return {
        "reply_text": reply_text,
        "requires_human_approval": requires_human_approval,
        "ok": True,
    }


# ── Routers ────────────────────────────────────────────────────────────────────

def _route_after_supervisor(state: MemberChatState) -> str:
    return state.get("route") or "direct_reply"


def _after_resolve(state: MemberChatState) -> str:
    return "denied" if state.get("route") == "denied" else "load_context"


# ── Graph factory ──────────────────────────────────────────────────────────────

def build_graph():
    from langgraph.graph import END, StateGraph
    builder = StateGraph(MemberChatState)

    builder.add_node("resolve_member",         resolve_member)
    builder.add_node("load_context",           load_context)
    builder.add_node("supervisor",             supervisor)
    builder.add_node("company_ops",            company_ops_dispatch)
    builder.add_node("lawfirm_marketing",      lawfirm_marketing_dispatch)
    builder.add_node("lawfirm_sales",          lawfirm_sales_dispatch)
    builder.add_node("direct_reply",           direct_reply)
    builder.add_node("emit_audit",             emit_audit)

    builder.set_entry_point("resolve_member")

    builder.add_conditional_edges(
        "resolve_member", _after_resolve,
        {"denied": "direct_reply", "load_context": "load_context"},
    )
    builder.add_edge("load_context", "supervisor")
    builder.add_conditional_edges(
        "supervisor", _route_after_supervisor,
        {
            "company_ops":       "company_ops",
            "lawfirm_marketing": "lawfirm_marketing",
            "lawfirm_sales":     "lawfirm_sales",
            "direct_reply":      "direct_reply",
            "escalate":          "direct_reply",
        },
    )
    for n in ("company_ops", "lawfirm_marketing", "lawfirm_sales"):
        builder.add_edge(n, "direct_reply")
    builder.add_edge("direct_reply", "emit_audit")
    builder.add_edge("emit_audit", END)

    return builder.compile()
