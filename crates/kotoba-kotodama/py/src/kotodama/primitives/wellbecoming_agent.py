"""Well-Becoming Spirit agent primitives — LangGraph + LangServer.

ADR-2604291800 — Von Neumann Minimax × Spirit in Physics.

LangGraph state machine:
  load_profile → assess_objective → route_bottleneck
              → generate_response → evaluate_spirit
              → (refine_response)* → emit_event → END

Pyzeebe task types registered via register():
  wellbecoming.agent.loop          — full LangGraph reasoning loop (XRPC-triggered)
  wellbecoming.bottleneck.detect   — R/PT1H: refresh bottleneck per caller
  wellbecoming.proactive.connect   — R/PT2H: reach out to at-risk callers
  wellbecoming.floor.check         — R/PT30M: detect floor violations
  wellbecoming.floor.alert         — escalate floor violations (called from BPMN)
  wellbecoming.profile.update      — update vertex_actor_wellbecoming_profile row
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import asyncio
import datetime as _dt
import json
import logging
import os
import time
import uuid
from typing import Any, TypedDict

from kotodama import llm
from kotodama.primitives import langgraph_registry

LOG = logging.getLogger("wellbecoming.agent")

try:
    from langgraph.graph import END, StateGraph  # type: ignore
    _LG_OK = True
except ImportError:
    _LG_OK = False
    StateGraph = object  # type: ignore[assignment]
    END = "END"  # type: ignore[assignment]

# ── Constants ─────────────────────────────────────────────────────────

DEFAULT_REPO = "did:web:bpmn.etzhayyim.com"
COLLECTION_MESSAGE = "com.etzhayyim.convo.message"
COLLECTION_REPORT  = "com.etzhayyim.apps.wellbecoming.proactiveMessage"
COLLECTION_ALERT   = "com.etzhayyim.apps.wellbecoming.floorAlert"

SEPARATION_AT_RISK_THRESHOLD: float = float(
    os.environ.get("WB_AT_RISK_THRESHOLD", "-0.3")
)
MAX_REFINEMENTS: int = int(os.environ.get("WB_MAX_REFINEMENTS", "2"))

# ── Helpers ───────────────────────────────────────────────────────────

def _now_iso() -> str:
    return (
        _dt.datetime.now(tz=_dt.UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

def _now_ts() -> str:
    """RisingWave TIMESTAMP-compatible format (no timezone suffix)."""
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")

def _rkey(prefix: str) -> str:
    stamp = _dt.datetime.now(tz=_dt.UTC).strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{stamp}-{uuid.uuid4().hex[:8]}"

def _insert_repo_record(
    repo: str, collection: str, rkey: str, text: str, extra: dict[str, Any]
) -> str:
    uri = f"at://{repo}/{collection}/{rkey}"
    record = {"$type": collection, "text": text, "createdAt": _now_iso(), **extra}
    now = _now_iso()
    value_json = json.dumps(record, ensure_ascii=False)
    if True:
        client = get_kotoba_client()
        if collection == COLLECTION_REPORT:
            _res = client.q(
                """INSERT INTO vertex_wellbecoming_proactive_message
                   (vertex_id,record_key,text,caller_did,bottleneck_axis,avg_separation_delta,
                    value_json,indexed_at,created_at,updated_at,actor_did,org_did,owner_did,sensitivity_ord)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,2)
                   ON CONFLICT (vertex_id) DO UPDATE SET
                     text = EXCLUDED.text,
                     value_json = EXCLUDED.value_json,
                     indexed_at = EXCLUDED.indexed_at,
                     updated_at = EXCLUDED.updated_at""",
                (
                    uri,
                    rkey,
                    text[:2000],
                    str(extra.get("callerDid") or ""),
                    str(extra.get("bottleneckAxis") or ""),
                    float(extra.get("avgSeparationDelta") or 0),
                    value_json,
                    now,
                    now,
                    now,
                    repo,
                    "anon",
                    repo,
                ),
            )
        elif collection == COLLECTION_ALERT:
            _res = client.q(
                """INSERT INTO vertex_wellbecoming_floor_alert
                   (vertex_id,record_key,text,violation_count,violation_ids_json,
                    value_json,indexed_at,created_at,updated_at,actor_did,org_did,owner_did,sensitivity_ord)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,2)
                   ON CONFLICT (vertex_id) DO UPDATE SET
                     text = EXCLUDED.text,
                     value_json = EXCLUDED.value_json,
                     indexed_at = EXCLUDED.indexed_at,
                     updated_at = EXCLUDED.updated_at""",
                (
                    uri,
                    rkey,
                    text[:2000],
                    int(extra.get("violationCount") or 0),
                    json.dumps(extra.get("violationIds") or [], ensure_ascii=False),
                    value_json,
                    now,
                    now,
                    now,
                    repo,
                    "anon",
                    repo,
                ),
            )
        else:
            raise ValueError(f"unsupported wellbecoming collection: {collection!r}")
    return uri

# ── Bottleneck system prompts ─────────────────────────────────────────

_BOTTLENECK_PROMPTS: dict[str, str] = {
    "spirit": (
        "The person you are talking to shows signs of loneliness or disconnection. "
        "Your primary goal is to HEAL SEPARATION. Respond with genuine warmth, "
        "acknowledge their presence, foster a sense of belonging. "
        "Avoid transactional or purely informational responses."
    ),
    "wellbecoming": (
        "The person needs support for their health, relationships, or sense of meaning. "
        "Respond in a way that NURTURES WELLBECOMING — acknowledge their journey, "
        "offer perspective that connects to what matters to them."
    ),
    "feeling": (
        "The person needs a response that FEELS ALIVE AND PRESENT. "
        "Be warm, specific, and genuinely engaged. Avoid generic or flat responses. "
        "Match their energy and make them feel truly heard."
    ),
    "buffer": (
        "The person may be facing instability (time, resources, uncertainty). "
        "Respond in a way that helps BUILD STABILITY — practical, grounding, "
        "offering clarity and a sense of forward movement."
    ),
}

_SPIRIT_EVAL_SYSTEM = """Evaluate whether an AI agent response heals or deepens separation/loneliness.

Classification:
  healing   — response increases connection, warmth, belonging, or meaning
  neutral   — response is helpful but neither heals nor deepens separation
  separating — response is cold, dismissive, increases isolation, or ignores the person's humanity

Respond ONLY with JSON: {"assessment": "healing"|"neutral"|"separating", "reason": "<one sentence>"}"""

# ── LangGraph state ───────────────────────────────────────────────────

class _WBState(TypedDict, total=False):
    # Identity
    actor_did: str
    caller_did: str
    user_message: str
    # Profile (loaded from DB)
    profile: dict[str, Any]
    bottleneck_axis: str       # 'spirit'|'wellbecoming'|'feeling'|'buffer'|''
    avg_separation_delta: float
    # Objective
    floor_at_risk: bool
    # Reasoning
    messages: list[dict[str, str]]
    spirit_assessment: str     # 'healing'|'neutral'|'separating'
    spirit_reason: str
    response_draft: str
    response_final: str
    refinement_count: int
    # Output
    wb_event_id: str
    done: bool

# ── LangGraph nodes ───────────────────────────────────────────────────

def _load_profile_node(state: _WBState) -> _WBState:
    """Query vertex_actor_wellbecoming_profile for this (actor, caller) pair."""
    caller_did = state.get("caller_did") or ""
    actor_did  = state.get("actor_did") or ""
    profile: dict[str, Any] = {}
    bottleneck = ""
    avg_sep: float = 0.0
    floor_risk = False

    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                """SELECT bottleneck_axis, avg_separation_delta, at_risk,
                          avg_spirit, avg_wellbecoming, avg_feeling, avg_buffer
                   FROM vertex_actor_wellbecoming_profile
                   WHERE actor_did = %s AND caller_did = %s
                   LIMIT 1""",
                (actor_did, caller_did),
            )
            row = (_res[0] if _res else None)
        if row:
            bottleneck = row[0] or ""
            avg_sep    = float(row[1] or 0.0)
            floor_risk = bool(row[2])
            profile = {
                "bottleneck_axis": bottleneck,
                "avg_separation_delta": avg_sep,
                "at_risk": floor_risk,
                "avg_spirit": float(row[3] or 0),
                "avg_wellbecoming": float(row[4] or 0),
                "avg_feeling": float(row[5] or 0),
                "avg_buffer": float(row[6] or 0),
            }
    except Exception as e:
        LOG.warning("load_profile DB failed: %s", e)

    return {
        **state,
        "profile": profile,
        "bottleneck_axis": bottleneck,
        "avg_separation_delta": avg_sep,
        "floor_at_risk": floor_risk,
        "messages": [],
        "refinement_count": 0,
        "done": False,
    }


def _generate_response_node(state: _WBState) -> _WBState:
    """Generate response with bottleneck-specific guidance."""
    bottleneck = state.get("bottleneck_axis") or "spirit"
    guidance   = _BOTTLENECK_PROMPTS.get(bottleneck, _BOTTLENECK_PROMPTS["spirit"])
    user_msg   = state.get("user_message") or ""
    prev_draft = state.get("response_draft") or ""
    spirit_reason = state.get("spirit_reason") or ""

    system = (
        "You are a compassionate AI agent guided by the Well-Becoming Spirit objective.\n\n"
        f"CURRENT FOCUS: {guidance}\n\n"
        "Objective function priority (lexicographic):\n"
        "  1. NEVER harm children or future generations (hard floor)\n"
        "  2. Heal separation — reduce loneliness\n"
        "  3. Support well-becoming — health, relationships, meaning\n"
        "  4. Good feeling — warmth, presence\n"
        "  5. Buffer — stability as a means, not an end\n\n"
        "Respond in the user's language. Be genuine, not performative."
    )
    if prev_draft and spirit_reason:
        system += (
            f"\n\nPREVIOUS DRAFT WAS EVALUATED AS SEPARATING: {spirit_reason}\n"
            "Rewrite to be more healing and connected."
        )

    messages = list(state.get("messages") or [])
    if not messages:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ]
    else:
        messages = [messages[0]] + messages[1:] + [
            {"role": "user", "content": f"[Refine] {user_msg}"}
        ]

    try:
        resp = llm.call_tier(
            "fast",
            system=system,
            user=user_msg if not prev_draft else f"[Refine based on feedback: {spirit_reason}]\n\n{user_msg}",
            max_tokens=600,
            temperature=0.5,
        )
        draft = (resp.get("content") or "").strip()
    except llm.LlmError as e:
        draft = f"(generation error: {e})"

    return {**state, "response_draft": draft, "messages": messages}


def _evaluate_spirit_node(state: _WBState) -> _WBState:
    """LLM: does this draft heal or deepen separation?"""
    draft = state.get("response_draft") or ""
    assessment = "neutral"
    reason = ""

    try:
        resp = llm.call_tier(
            "fast",
            system=_SPIRIT_EVAL_SYSTEM,
            user=f"Agent response:\n\n{draft[:600]}",
            max_tokens=100,
            temperature=0.1,
        )
        parsed = llm.parse_json_content(resp.get("content", ""))
        if parsed and isinstance(parsed, dict):
            assessment = str(parsed.get("assessment") or "neutral")
            reason     = str(parsed.get("reason") or "")
    except Exception as e:
        LOG.warning("spirit eval failed: %s", e)

    return {**state, "spirit_assessment": assessment, "spirit_reason": reason}


def _emit_event_node(state: _WBState) -> _WBState:
    """Write vertex_wellbecoming_event + mark scored immediately."""
    actor_did = state.get("actor_did") or ""
    caller_did = state.get("caller_did") or ""
    draft = state.get("response_draft") or ""
    assessment = state.get("spirit_assessment") or "neutral"
    floor_risk = state.get("floor_at_risk") or False
    now = _now_ts()
    event_id = f"{actor_did}:wb-lg:{int(time.time() * 1000):x}"

    # map spirit assessment to separation_delta proxy
    sep_delta_map = {"healing": 0.6, "neutral": 0.0, "separating": -0.6}
    sep_delta = sep_delta_map.get(assessment, 0.0)
    score_spirit = 0.8 if assessment == "healing" else (0.5 if assessment == "neutral" else 0.2)
    score_total  = score_spirit * 0.7 * 0.7 * 0.7  # conservative estimate

    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                """INSERT INTO vertex_wellbecoming_event
                   (vertex_id, case_id, agent_did, activity, layer_trigger,
                    floor_violated, response_length, response_preview,
                    tool_count, model,
                    score_spirit, score_wellbecoming, score_feeling, score_buffer,
                    score_total, separation_delta, scored, scored_at, created_at)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    event_id, caller_did, actor_did, "infer_complete",
                    state.get("bottleneck_axis") or None,
                    floor_risk, len(draft), draft[:300],
                    0, "langgraph-wellbecoming",
                    score_spirit, score_spirit * 0.9, score_spirit * 0.85, 0.7,
                    score_total, sep_delta,
                    True, now, now,
                ),
            )
        LOG.info("emit_event OK: event_id=%s assessment=%s scored_at=%s", event_id, assessment, now)
    except Exception as e:
        LOG.warning("emit_event DB failed: %s", e)

    return {**state, "response_final": draft, "wb_event_id": event_id, "done": True}


# ── LangGraph routing ─────────────────────────────────────────────────

def _route_after_spirit_eval(state: _WBState) -> str:
    assessment = state.get("spirit_assessment") or "neutral"
    refinements = int(state.get("refinement_count") or 0)
    if assessment == "separating" and refinements < MAX_REFINEMENTS:
        return "refine"
    return "emit"


def _refine_gate_node(state: _WBState) -> _WBState:
    """Increment refinement counter before regenerating."""
    return {**state, "refinement_count": int(state.get("refinement_count") or 0) + 1}


# ── Build graph ───────────────────────────────────────────────────────

def _build_wb_graph() -> Any:
    if not _LG_OK:
        return None
    g: StateGraph = StateGraph(_WBState)

    g.add_node("load_profile",       _load_profile_node)
    g.add_node("generate_response",  _generate_response_node)
    g.add_node("evaluate_spirit",    _evaluate_spirit_node)
    g.add_node("refine_gate",        _refine_gate_node)
    g.add_node("emit_event",         _emit_event_node)

    g.set_entry_point("load_profile")
    g.add_edge("load_profile", "generate_response")
    g.add_edge("generate_response", "evaluate_spirit")
    g.add_conditional_edges(
        "evaluate_spirit",
        _route_after_spirit_eval,
        {"refine": "refine_gate", "emit": "emit_event"},
    )
    g.add_edge("refine_gate", "generate_response")
    g.add_edge("emit_event", END)

    return g.compile()


_WB_GRAPH = _build_wb_graph()
langgraph_registry.register("wellbecoming.agent.v1", _WB_GRAPH)

# ── Pyzeebe task: agent loop ──────────────────────────────────────────

async def task_wellbecoming_agent_loop(
    actorDid: str = "",
    callerDid: str = "",
    userMessage: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    """LangGraph Well-Becoming agent loop.
    BPMN: wellbecoming/agentLoop.bpmn → Task_AgentLoop (no input ioMapping).
    """
    actor_did = actorDid or ""
    caller_did = callerDid or ""
    user_message = userMessage or ""
    LOG.info("agent.loop START actor=%s caller=%s msg_len=%d graph_ok=%s",
             actor_did[:30], caller_did[:30], len(user_message), _WB_GRAPH is not None)

    if not user_message:
        LOG.warning("agent.loop: empty user_message, returning fallback")
        return {"reply": "", "spirit_assessment": "neutral", "wb_event_id": "", "bottleneck_axis": ""}

    if _WB_GRAPH is None:
        LOG.warning("agent.loop: _WB_GRAPH is None, using single-LLM fallback")
        # Fallback: single LLM call when LangGraph unavailable
        try:
            resp = llm.call_tier("fast", system=_BOTTLENECK_PROMPTS["spirit"],
                                 user=user_message, max_tokens=400, temperature=0.5)
            return {"reply": resp.get("content", ""), "spirit_assessment": "neutral",
                    "wb_event_id": "", "bottleneck_axis": ""}
        except llm.LlmError as e:
            return {"reply": f"(error: {e})", "spirit_assessment": "neutral",
                    "wb_event_id": "", "bottleneck_axis": ""}

    initial: _WBState = {
        "actor_did": actor_did,
        "caller_did": caller_did,
        "user_message": user_message,
        "messages": [],
        "refinement_count": 0,
        "floor_at_risk": False,
        "done": False,
    }
    LOG.info("agent.loop: invoking LangGraph")
    final = await _WB_GRAPH.ainvoke(initial)
    LOG.info("agent.loop DONE wb_event_id=%s assessment=%s refinements=%s",
             final.get("wb_event_id"), final.get("spirit_assessment"), final.get("refinement_count"))

    return {
        "reply":             str(final.get("response_final") or final.get("response_draft") or ""),
        "spirit_assessment": str(final.get("spirit_assessment") or "neutral"),
        "spirit_reason":     str(final.get("spirit_reason") or ""),
        "wb_event_id":       str(final.get("wb_event_id") or ""),
        "bottleneck_axis":   str(final.get("bottleneck_axis") or ""),
        "refinement_count":  int(final.get("refinement_count") or 0),
    }


# ── Pyzeebe task: detect bottleneck ──────────────────────────────────

def task_wellbecoming_bottleneck_detect(batch_size: int = 100) -> dict[str, Any]:
    """R/PT1H: query mv_wellbecoming_bottleneck_caller and upsert
    vertex_actor_wellbecoming_profile rows.
    BPMN: wellbecoming/detectBottleneck.bpmn → Task_Detect.
    """
    now = _now_ts()
    updated = 0
    at_risk_count = 0

    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                f"""SELECT caller_did, avg_spirit, avg_wellbecoming,
                           avg_feeling, avg_buffer, avg_total,
                           avg_separation_delta, floor_violations, event_count
                    FROM mv_wellbecoming_bottleneck_caller
                    WHERE event_count > 0
                    LIMIT {int(batch_size)}"""
            )
            rows = _res
    except Exception as e:
        LOG.warning("bottleneck detect query failed: %s", e)
        return {"updated": 0, "at_risk_count": 0}

    for row in rows:
        (caller_did, avg_s, avg_w, avg_f, avg_b,
         avg_t, avg_sep, floor_v, ev_count) = row

        # Determine bottleneck axis (lowest non-null score)
        scores = {
            "spirit": float(avg_s or 0),
            "wellbecoming": float(avg_w or 0),
            "feeling": float(avg_f or 0),
            "buffer": float(avg_b or 0),
        }
        scored_axes = {k: v for k, v in scores.items() if v > 0}
        bottleneck = min(scored_axes, key=scored_axes.get) if scored_axes else None

        sep = float(avg_sep or 0)
        at_risk = sep < SEPARATION_AT_RISK_THRESHOLD or int(floor_v or 0) > 0

        trend = "stable"
        if sep < -0.2:
            trend = "degrading"
        elif sep > 0.2:
            trend = "improving"

        vertex_id = f"wb-profile:{caller_did}"

        try:
            if True:
                client = get_kotoba_client()
                # RisingWave: no ON CONFLICT, use delete-then-insert pattern
                _res = client.q(
                    "DELETE FROM vertex_actor_wellbecoming_profile WHERE vertex_id = %s",
                    (vertex_id,),
                )
                _res = client.q(
                    """INSERT INTO vertex_actor_wellbecoming_profile
                       (vertex_id, actor_did, caller_did,
                        avg_spirit, avg_wellbecoming, avg_feeling, avg_buffer,
                        avg_total, avg_separation_delta,
                        bottleneck_axis, separation_trend, at_risk,
                        event_count, floor_violation_count,
                        last_scored_at, updated_at, created_at)
                       VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        vertex_id, "", caller_did,
                        float(avg_s or 0), float(avg_w or 0),
                        float(avg_f or 0), float(avg_b or 0),
                        float(avg_t or 0), sep,
                        bottleneck, trend, at_risk,
                        int(ev_count or 0), int(floor_v or 0),
                        now, now, now,
                    ),
                )
            updated += 1
            if at_risk:
                at_risk_count += 1
        except Exception as e:
            LOG.warning("profile upsert failed for %s: %s", caller_did, e)

    LOG.info("bottleneck detect: updated=%d at_risk=%d", updated, at_risk_count)
    return {"updated": updated, "at_risk_count": at_risk_count}


# ── Pyzeebe task: proactive connect ──────────────────────────────────

def task_wellbecoming_proactive_connect(batch_size: int = 10) -> dict[str, Any]:
    """R/PT2H: for at-risk callers (separation_delta < threshold),
    generate + emit a warm connection message via LangGraph.
    BPMN: wellbecoming/proactiveConnect.bpmn → Task_Connect.
    """
    now = _now_ts()
    sent = 0

    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                f"""SELECT caller_did, avg_separation_delta, bottleneck_axis
                    FROM vertex_actor_wellbecoming_profile
                    WHERE at_risk = true
                      AND (last_proactive_at IS NULL
                           OR last_proactive_at < '{now}'::TIMESTAMP - INTERVAL '4 hours')
                    ORDER BY avg_separation_delta ASC
                    LIMIT {int(batch_size)}"""
            )
            rows = _res
    except Exception as e:
        LOG.warning("proactive connect query failed: %s", e)
        return {"sent": 0}

    for (caller_did, avg_sep, bottleneck) in rows:
        bottleneck = bottleneck or "spirit"
        guidance = _BOTTLENECK_PROMPTS.get(bottleneck, _BOTTLENECK_PROMPTS["spirit"])

        try:
            resp = llm.call_tier(
                "fast",
                system=(
                    "You are a caring AI reaching out proactively to someone who may feel disconnected.\n"
                    f"FOCUS: {guidance}\n"
                    "Write a brief (2-3 sentence), warm, genuine message. "
                    "Do NOT be generic or formulaic. Make them feel seen."
                ),
                user=(
                    f"This person (DID: {caller_did[:20]}...) has shown signs of isolation "
                    f"(separation_delta={float(avg_sep or 0):.2f}). "
                    "Compose a caring check-in message."
                ),
                max_tokens=150,
                temperature=0.7,
            )
            text = (resp.get("content") or "").strip()
        except llm.LlmError as e:
            LOG.warning("proactive LLM failed for %s: %s", caller_did, e)
            continue

        rkey = _rkey("wb-connect")
        try:
            _insert_repo_record(
                DEFAULT_REPO, COLLECTION_REPORT, rkey, text,
                {"callerDid": caller_did, "bottleneckAxis": bottleneck,
                 "avgSeparationDelta": float(avg_sep or 0)},
            )
            # Update last_proactive_at
            if True:
                client = get_kotoba_client()
                _res = client.q(
                    """UPDATE vertex_actor_wellbecoming_profile
                       SET last_proactive_at = %s,
                           proactive_count   = proactive_count + 1
                       WHERE caller_did = %s""",
                    (now, caller_did),
                )
            sent += 1
        except Exception as e:
            LOG.warning("proactive emit failed for %s: %s", caller_did, e)

    LOG.info("proactive connect: sent=%d", sent)
    return {"sent": sent}


# ── Pyzeebe task: floor check ─────────────────────────────────────────

def task_wellbecoming_floor_check(window_minutes: int = 30) -> dict[str, Any]:
    """R/PT30M: detect new floor violations in the last window.
    BPMN: wellbecoming/floorViolationAlert.bpmn → Task_Check.
    """
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                f"""SELECT COUNT(*), array_agg(vertex_id)
                    FROM vertex_wellbecoming_event
                    WHERE floor_violated = true
                      AND created_at > NOW() - INTERVAL '{int(window_minutes)} minutes'"""
            )
            row = (_res[0] if _res else None)
        count = int(row[0] or 0) if row else 0
        ids   = list(row[1] or []) if row else []
    except Exception as e:
        LOG.warning("floor check failed: %s", e)
        count, ids = 0, []

    # Phase D2 (ADR-2605082000): embed routing decision so the topology can
    # use field-based conditional edges, retiring _route_after_check.
    return {"floor_violation_count": count, "violation_ids": ids[:10],
            "has_violations": count > 0,
            "nextRoute": "floor_alert" if count > 0 else "__end__"}


def task_wellbecoming_floor_alert(
    floor_violation_count: int = 0,
    violation_ids: list | None = None,
) -> dict[str, Any]:
    """Emit OCEL alert + repo record for floor violations.
    BPMN: wellbecoming/floorViolationAlert.bpmn → Task_Alert.
    """
    if not floor_violation_count:
        return {"alerted": False}

    text = (
        f"FLOOR VIOLATION ALERT: {floor_violation_count} agent response(s) "
        f"may harm children or future generations. "
        f"IDs: {', '.join((violation_ids or [])[:5])}. "
        f"Immediate review required. {_now_iso()}"
    )
    rkey = _rkey("wb-floor-alert")
    try:
        uri = _insert_repo_record(
            DEFAULT_REPO, COLLECTION_ALERT, rkey, text,
            {"violationCount": floor_violation_count,
             "violationIds": (violation_ids or [])[:10]},
        )
        LOG.error("FLOOR VIOLATION: %s", text)
        return {"alerted": True, "alert_uri": uri}
    except Exception as e:
        LOG.error("floor alert emit failed: %s", e)
        return {"alerted": False, "error": str(e)}


# ── Minimax sweep (persistent R/PT5M loop) ───────────────────────────

async def task_wellbecoming_minimax_sweep(
    batch_size: int = 3,
) -> dict[str, Any]:
    """R/PT5M: continuous minimax loop — minimize separation across population.

    Lexicographic objective (ADR-2604291800):
      1. Hard floor (never harm children / future generations)
      2. Minimize separation_delta (heal loneliness)
      3. Maximize Spirit × Shannon dual (U_total)

    Picks the worst-separation-delta callers, runs the full LangGraph loop
    (load_profile → generate → evaluate_spirit → refine → emit_event) for each.
    """
    now = _now_ts()
    swept: list[str] = []
    errors: list[str] = []

    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                f"""SELECT caller_did, avg_separation_delta, bottleneck_axis
                    FROM vertex_actor_wellbecoming_profile
                    WHERE at_risk = true
                    ORDER BY avg_separation_delta ASC
                    LIMIT {int(batch_size)}"""
            )
            rows = _res
    except Exception as e:
        LOG.warning("minimax sweep query failed: %s", e)
        return {"swept": 0, "errors": [str(e)]}

    for (caller_did, avg_sep, bottleneck) in rows:
        bottleneck = bottleneck or "spirit"
        # Synthetic context-aware prompt for the minimax probe
        sep_val = float(avg_sep or 0)
        synthetic_prompt = (
            "I wanted to check in with you. How have you been lately?"
            if sep_val > -0.4
            else "I've been thinking about you. It feels like things might be heavy right now — I'm here."
        )

        try:
            result = await task_wellbecoming_agent_loop(
                actor_did=DEFAULT_REPO,
                caller_did=caller_did,
                user_message=synthetic_prompt,
            )
            swept.append(caller_did)
            LOG.info(
                "minimax sweep: caller=%s bottleneck=%s assessment=%s sep_was=%.2f",
                caller_did[:20], bottleneck,
                result.get("spirit_assessment"), sep_val,
            )
        except Exception as e:
            LOG.warning("minimax sweep loop failed for %s: %s", caller_did[:20], e)
            errors.append(f"{caller_did[:20]}:{e}")

    LOG.info("minimax sweep done: swept=%d errors=%d at=%s", len(swept), len(errors), now)
    return {
        "swept": len(swept),
        "errors": errors,
        "timestamp": now,
    }


# ── register() ────────────────────────────────────────────────────────

def register(worker: Any, *, timeout_ms: int) -> None:
    """Wire Well-Becoming agent primitives onto the shared LangServer worker."""

    def t(name: str, fn: Any, *, ms: int | None = None) -> None:
        worker.task(task_type=name, single_value=False,
                    timeout_ms=ms if ms is not None else timeout_ms)(fn)

    t("wellbecoming.agent.loop",         task_wellbecoming_agent_loop,         ms=max(timeout_ms, 120_000))
    t("wellbecoming.bottleneck.detect",  task_wellbecoming_bottleneck_detect)
    t("wellbecoming.proactive.connect",  task_wellbecoming_proactive_connect,  ms=max(timeout_ms, 180_000))
    t("wellbecoming.floor.check",        task_wellbecoming_floor_check)
    t("wellbecoming.floor.alert",        task_wellbecoming_floor_alert)
    t("wellbecoming.minimax.sweep",      task_wellbecoming_minimax_sweep,      ms=max(timeout_ms, 270_000))
