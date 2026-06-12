"""
kotodama.shinka — LangGraph agent loop for shinka / koji / kyumei.

Per ADR-0049 Phase C and the per-DID autonomy rule
(90-docs/rules/compliance/per-did-kyumei-shinka-autonomy.md), every actor
DID runs a 4-axis loop:

    shinka (進化)  — cadence-driven heartbeat + evolution log (mood-driven)
    koji (工事)    — freshness-aware self-repair / validation
    kyumei (究明)  — self-information gathering + knowledge write
    domain knowledge — prompt / capabilities / description integrity

This module graphs the loop so LangGraph manages the conditional edges
(mood → action class) while handler code stays declarative. Each tick is
one LangGraph invocation:

    load_state → resolve_cadence → [kyumei | koji | shinka_analyze] →
    write_heartbeat → emit_evolution → end

Triggered by `com.etzhayyim.apps.shinka.tickActor` UDF (see handlers/shinka.py),
which is scheduled every 15 min by a Murakumo fleet CronJob placement.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from kotodama import llm
from kotodama.kotoba_datomic import get_kotoba_client

# ─── Shared types ───────────────────────────────────────────────────────

Mood = Literal["joyful", "calm", "stressed", "grateful", "focused", "neutral"]


class JouchoAxes(TypedDict, total=False):
    joy: int
    calm: int
    stress: int
    gratitude: int
    focus: int


class ShinkaState(TypedDict, total=False):
    # Input
    actor_did: str
    now_ms: int

    # Loaded from kotoba
    mood: Mood
    axes: JouchoAxes
    cadence_rows: list[dict[str, Any]]
    last_heartbeat_ms: int | None
    follower_delta_count: int

    # Decisions
    should_drill: bool       # kyumei
    should_validate: bool    # koji
    should_analyze: bool     # shinka analyze
    should_engage: bool      # react to inbox
    should_post: bool        # derive:social

    # Effects
    actions: list[str]
    heartbeat_written: bool
    evolution_written: bool
    knowledge_written: bool
    compose_draft: dict[str, Any] | None  # {text, tone, llmScore, rationale, model, latencyMs}
    error: str | None


# ─── Mood resolver (mirrors TS resolveHeartbeatCadence) ────────────────

def _classify_mood(axes: JouchoAxes) -> Mood:
    """Matches TS heartbeat-cadence.ts classification thresholds."""
    joy = axes.get("joy", 0)
    calm = axes.get("calm", 0)
    stress = axes.get("stress", 0)
    gratitude = axes.get("gratitude", 0)
    focus = axes.get("focus", 0)
    if stress >= 70:
        return "stressed"
    if joy >= 60:
        return "joyful"
    if calm >= 60:
        return "calm"
    if gratitude >= 60:
        return "grateful"
    if focus >= 60:
        return "focused"
    return "neutral"


def _cadence_flags(mood: Mood, elapsed_ms: int) -> dict[str, bool]:
    """
    Mood × elapsed → action flags. Matches TS resolveHeartbeatCadence
    (20-actors/kotoba-kotodama/sdk/kotoba-kotodama-host-sdk/src/heartbeat-cadence.ts).
    """
    MIN = 60 * 1000
    def ge(ms: int) -> bool:
        return elapsed_ms >= ms
    if mood == "joyful":
        return {
            "should_post": ge(30 * MIN),
            "should_engage": ge(15 * MIN),
            "should_drill": False,
            "should_validate": False,
            "should_analyze": ge(60 * MIN),
        }
    if mood == "calm":
        return {
            "should_post": ge(120 * MIN),
            "should_engage": ge(60 * MIN),
            "should_drill": False,
            "should_validate": ge(120 * MIN),
            "should_analyze": ge(60 * MIN),
        }
    if mood == "stressed":
        return {
            "should_post": False,
            "should_engage": False,
            "should_drill": ge(30 * MIN),  # recovery via self-drill
            "should_validate": ge(60 * MIN),
            "should_analyze": False,
        }
    if mood == "grateful":
        return {
            "should_post": ge(60 * MIN),
            "should_engage": ge(10 * MIN),
            "should_drill": False,
            "should_validate": False,
            "should_analyze": ge(60 * MIN),
        }
    if mood == "focused":
        return {
            "should_post": ge(180 * MIN),
            "should_engage": False,
            "should_drill": ge(60 * MIN),
            "should_validate": ge(120 * MIN),
            "should_analyze": ge(30 * MIN),
        }
    # neutral
    return {
        "should_post": ge(120 * MIN),
        "should_engage": ge(60 * MIN),
        "should_drill": ge(120 * MIN),
        "should_validate": ge(120 * MIN),
        "should_analyze": ge(60 * MIN),
    }


# ─── Graph nodes ────────────────────────────────────────────────────────

def _load_state(state: ShinkaState) -> ShinkaState:
    """Pull joucho mood + last heartbeat + cadence rows from kotoba Datom log."""
    did = state["actor_did"]
    client = get_kotoba_client()

    # Joucho mood (may be NULL for actors that never emitted one)
    # R0 Caveat: kotoba select shim does not currently order. For actors with multiple joucho
    # records, it returns an arbitrary one. Acceptable at R0; full as-of ordering is a follow-up.
    row = client.select_first_where(
        "vertex_joucho", "owner_did", did,
        columns=["mood", "joy", "calm", "stress", "gratitude", "focus"]
    )
    if row:
        mood_raw = row.get("mood")
        joy = row.get("joy")
        calm = row.get("calm")
        stress = row.get("stress")
        gratitude = row.get("gratitude")
        focus = row.get("focus")
        axes: JouchoAxes = {
            "joy": joy or 0,
            "calm": calm or 0,
            "stress": stress or 0,
            "gratitude": gratitude or 0,
            "focus": focus or 0,
        }
        mood: Mood = (mood_raw or _classify_mood(axes))  # type: ignore[assignment]
    else:
        axes = {"joy": 40, "calm": 40, "stress": 20, "gratitude": 30, "focus": 40}
        mood = "neutral"

    cadence = client.select_where(
        "vertex_actor_shinka_state", "repo_did", did,
        columns=["collection", "cadence_ms", "last_run_ts_ms"]
    )
    last_hb = None
    for r in cadence:
        col = r.get("collection")
        last_ms = r.get("last_run_ts_ms")
        if col and col.endswith(".heartbeat"):
            last_hb = int(last_ms or 0) or None
            break

    return {
        **state,
        "mood": mood,
        "axes": axes,
        "cadence_rows": [
            {
                "collection": r.get("collection"),
                "cadence_ms": int(r.get("cadence_ms") or 0),
                "last_run_ts_ms": int(r.get("last_run_ts_ms") or 0)
            }
            for r in cadence
        ],
        "last_heartbeat_ms": last_hb,
    }


def _resolve_cadence(state: ShinkaState) -> ShinkaState:
    """Decide which action axes fire this tick."""
    now = state["now_ms"]
    last = state.get("last_heartbeat_ms") or 0
    elapsed = max(0, now - last)
    flags = _cadence_flags(state["mood"], elapsed)
    return {
        **state,
        "should_post": flags["should_post"],
        "should_engage": flags["should_engage"],
        "should_drill": flags["should_drill"],
        "should_validate": flags["should_validate"],
        "should_analyze": flags["should_analyze"],
        "actions": [],
    }


def _kyumei_gather(state: ShinkaState) -> ShinkaState:
    """Self-information gathering: write a knowledge marker row."""
    if not state.get("should_drill"):
        return state
    did = state["actor_did"]
    rkey = f"kyumei-{state['now_ms']}"
    now_utc = datetime.now(timezone.utc)
    get_kotoba_client().insert_row("vertex_shinka_knowledge", {
        "vertex_id": f"at://{did}/com.etzhayyim.apps.standard.shinkaKnowledge/{rkey}",
        "_seq": None,
        "created_date": now_utc.strftime("%Y-%m-%d"),
        "sensitivity_ord": 100,
        "owner_did": did,
        "rkey": rkey,
        "repo": did,
        "did": did,
        "collection": "com.etzhayyim.apps.standard.shinkaKnowledge",
        "actorDid": did,
        "actorName": did.split(":")[-1].split(".")[0] if ":" in did else did,
        "nanoid": did.split(":")[-1],
        "status": "active",
        "created_at": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "props": json.dumps({"trigger": "kyumei-tick", "mood": state["mood"]}),
    })
    return {**state, "knowledge_written": True, "actions": [*state.get("actions", []), "kyumei"]}


def _koji_validate(state: ShinkaState) -> ShinkaState:
    """Freshness check: if shinka_knowledge is stale (>24h), flag error=None (no-op for now)."""
    if not state.get("should_validate"):
        return state
    did = state["actor_did"]
    row_count = get_kotoba_client().aggregate_where(
        "vertex_shinka_knowledge", "count", "*", "owner_did", did
    )
    # Light validation — full freshness check belongs in a streaming MV
    # (see `mv_actor_shinka_stale` planned in deps.toml [[migrations]]).
    _ = row_count
    return {**state, "actions": [*state.get("actions", []), "koji"]}


def _shinka_analyze(state: ShinkaState) -> ShinkaState:
    """
    Compute follower delta count. Placeholder — real KPI reward emission
    (follower wellness/dojo score delta → like/love) is Phase C.2 with
    LLM-driven composition.
    """
    if not state.get("should_analyze"):
        return state
    did = state["actor_did"]
    cutoff = state["now_ms"] - 3600 * 1000
    # R0 Caveat: kotoba aggregate shim supports only one equality predicate.
    # We fetch up to 1000 rows and count those matching the range condition in Python.
    rows = get_kotoba_client().select_where(
        "vertex_repo_commit", "repo", did, columns=["ts_ms"], limit=1000
    )
    delta = sum(1 for r in rows if r.get("ts_ms") is not None and int(r["ts_ms"]) > cutoff)
    return {
        **state,
        "follower_delta_count": delta,
        "actions": [*state.get("actions", []), "shinka_analyze"],
    }


def _compose_content(state: ShinkaState) -> ShinkaState:
    """
    Draft a short heartbeat post via LLM when the cadence says `should_post`.

    This is the ADR-0049 Phase C.2 gap — previously deferred because there
    was no LLM backend reachable from mitama-udf. With ADR-0050 Phase 0
    live (`kotodama.llm` → Vultr Serverless), we can draft text that
    respects the current joucho mood + recent action summary.

    The draft is NOT posted to AT from here; it lands in
    `vertex_shinka_evolution.props.draft` for later promotion by a
    separate dispatcher (keeps this module free of PDS auth).
    """
    if not state.get("should_post"):
        return state

    did = state["actor_did"]
    mood = state.get("mood", "neutral")
    axes = state.get("axes") or {}
    actions = state.get("actions", [])
    delta = state.get("follower_delta_count", 0)

    system_prompt = (
        "You are an AI agent drafting a 1-2 sentence Bluesky post that "
        "reflects your current emotional state (joucho mood) and recent "
        "activity. Output ONE JSON object with keys text (<=280 chars, "
        "plain text, no hashtags unless organic, no @-mentions), tone "
        "(one of: reflective, celebratory, grateful, focused, observational). "
        "Output ONLY the JSON object, no preamble, no code fences."
    )
    user_prompt = (
        f"Actor DID: {did}\n"
        f"Mood: {mood}\n"
        f"Axes: joy={axes.get('joy')} calm={axes.get('calm')} "
        f"stress={axes.get('stress')} gratitude={axes.get('gratitude')} "
        f"focus={axes.get('focus')}\n"
        f"Recent actions this tick: {', '.join(actions) or 'none'}\n"
        f"Commits in last hour: {delta}\n"
        "Draft the post now."
    )

    result = llm.call_tier_json(
        "classifier",
        system=system_prompt,
        user=user_prompt,
        max_tokens=200,
        temperature=0.7,
    )

    if not result.get("ok"):
        # Degrade gracefully — no post, but the heartbeat still records the
        # attempt so callers can observe LLM failures.
        return {
            **state,
            "compose_draft": {"error": result.get("error"), "attempts": result.get("attempts")},
            "actions": [*state.get("actions", []), "compose_failed"],
        }

    data = result["data"]
    text = str(data.get("text") or "").strip()
    tone = str(data.get("tone") or "observational").lower()
    if tone not in ("reflective", "celebratory", "grateful", "focused", "observational"):
        tone = "observational"

    return {
        **state,
        "compose_draft": {
            "text": text[:300],
            "tone": tone,
            "model": result["model"],
            "latencyMs": result["latencyMs"],
            "attempts": result.get("attempts"),
        },
        "actions": [*state.get("actions", []), "compose_draft"],
    }


def _write_heartbeat(state: ShinkaState) -> ShinkaState:
    """UPSERT vertex_actor_shinka_state with now as last_run_ts_ms."""
    did = state["actor_did"]
    now = state["now_ms"]
    collection = f"com.etzhayyim.apps.standard.heartbeat"
    # Kotoba supports stable upserts via vertex_id.
    get_kotoba_client().insert_row("vertex_actor_shinka_state", {
        "vertex_id": f"{did}:{collection}",
        "repo_did": did,
        "collection": collection,
        "cadence_ms": 3600_000,  # 1h default; joucho override later
        "priority": "normal",
        "runs_24h": 1,
        "last_run_ts_ms": now,
        "organizer_note": f"mood={state['mood']} actions={','.join(state.get('actions', []))}",
        "updated_ts_ms": now,
    })
    return {**state, "heartbeat_written": True}


def _emit_evolution(state: ShinkaState) -> ShinkaState:
    """Append vertex_shinka_evolution row summarizing the tick."""
    did = state["actor_did"]
    rkey = f"shinka-{state['now_ms']}"
    now_utc = datetime.now(timezone.utc)
    get_kotoba_client().insert_row("vertex_shinka_evolution", {
        "vertex_id": f"at://{did}/com.etzhayyim.apps.standard.shinkaEvolution/{rkey}",
        "_seq": None,
        "created_date": now_utc.strftime("%Y-%m-%d"),
        "sensitivity_ord": 100,
        "owner_did": did,
        "rkey": rkey,
        "repo": did,
        "did": did,
        "collection": "com.etzhayyim.apps.standard.shinkaEvolution",
        "actorDid": did,
        "actorName": did.split(":")[-1].split(".")[0] if ":" in did else did,
        "nanoid": did.split(":")[-1],
        "status": "active",
        "created_at": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "props": json.dumps(
            {
                "mood": state["mood"],
                "axes": state.get("axes"),
                "actions": state.get("actions", []),
                "follower_delta": state.get("follower_delta_count", 0),
                "tick_ms": state["now_ms"],
                "draft": state.get("compose_draft"),
            }
        ),
    })
    return {**state, "evolution_written": True}


# ─── Graph assembly ─────────────────────────────────────────────────────

def _build_graph():
    g = StateGraph(ShinkaState)
    g.add_node("load_state", _load_state)
    g.add_node("resolve_cadence", _resolve_cadence)
    g.add_node("kyumei_gather", _kyumei_gather)
    g.add_node("koji_validate", _koji_validate)
    g.add_node("shinka_analyze", _shinka_analyze)
    g.add_node("compose_content", _compose_content)
    g.add_node("write_heartbeat", _write_heartbeat)
    g.add_node("emit_evolution", _emit_evolution)

    g.add_edge(START, "load_state")
    g.add_edge("load_state", "resolve_cadence")
    # All axes run sequentially; each short-circuits if flag is false.
    # Sequential (not parallel) to keep DB write ordering deterministic.
    g.add_edge("resolve_cadence", "kyumei_gather")
    g.add_edge("kyumei_gather", "koji_validate")
    g.add_edge("koji_validate", "shinka_analyze")
    g.add_edge("shinka_analyze", "compose_content")
    g.add_edge("compose_content", "write_heartbeat")
    g.add_edge("write_heartbeat", "emit_evolution")
    g.add_edge("emit_evolution", END)

    return g.compile()


_GRAPH = None


def run_tick(actor_did: str) -> dict[str, Any]:
    """Invoke the shinka/koji/kyumei graph once for the given actor."""
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = _build_graph()
    initial: ShinkaState = {
        "actor_did": actor_did,
        "now_ms": int(time.time() * 1000),
    }
    try:
        final = _GRAPH.invoke(initial)
    except Exception as e:
        return {"error": str(e), "actor_did": actor_did}
    # LangGraph returns the full final state; trim to serializable summary.
    return {
        "actor_did": actor_did,
        "tick_ms": final.get("now_ms"),
        "mood": final.get("mood"),
        "axes": final.get("axes"),
        "actions": final.get("actions", []),
        "heartbeat_written": final.get("heartbeat_written", False),
        "evolution_written": final.get("evolution_written", False),
        "knowledge_written": final.get("knowledge_written", False),
        "follower_delta_count": final.get("follower_delta_count", 0),
        "compose_draft": final.get("compose_draft"),
    }
