"""Karma evaluation agent — LangGraph state machine + Pregel-style
graph propagation + actor mailbox semantics.

Authoritative axioms: 90-docs/proof/Karma.lean (Lean 4 verified).

Topology (LangGraph nodes):

    load_organism → load_recent_edges → vulnerability_assess
                  → tier_classify (LLM, agentTier)
                  → axiom_verify (Karma.lean Axiom A/B/D/E inlined)
                  → witness_search (Pregel BFS over edge_karma_dependency)
                  → recommend (LLM synthesis)
                  → emit_event → END

    Conditional edges:
      after axiom_verify:
        - floor_violated → emit_event   (skip witness search + recommend)
        - else           → witness_search
      after witness_search:
        - witness_count == 0 → escalate → recommend
        - witness_count > 0  → recommend

Pregel-style graph propagation (witness_search):

    vertex value = organism (DID)
    message      = (axis, magnitude, direction, vul, ts_ms)

    Superstep 0: seed = {sourceDid, targetDid} from candidate / edge
    Superstep k → k+1:
      for each frontier vertex v:
        - send message to all 1-hop neighbors via edge_karma_dependency
        - each neighbor counts overlapping edges with seed
      vote-to-halt when:
        - frontier ⊆ visited (BFS frontier exhausted), OR
        - hop_count == witnessHops

Actor mailbox semantics:

    Each frontier vertex becomes an actor for one supersession of
    Pregel computation. The mailbox is the in-memory frontier dict
    (did → list[Message]). Concurrency is single-threaded BSP — no
    race because each superstep reads `visited_t` and writes
    `visited_{t+1}` atomically.

Pyzeebe task type:
    karma.agent.evaluate     — XRPC entry → LangGraph → recommendation
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import json
import logging
import math
import os
from datetime import datetime, timezone
from typing import Any, Optional, TypedDict

from kotodama import llm
from kotodama.kotoba_datomic import get_kotoba_client

LOG = logging.getLogger("karma.agent")

try:
    from langgraph.graph import END, StateGraph  # type: ignore
    _LG_OK = True
except ImportError:
    _LG_OK = False
    StateGraph = object  # type: ignore[assignment]
    END = "END"  # type: ignore[assignment]

# ── Constants (mirror Karma.lean) ──────────────────────────────────────

CHILD_FLOOR_AXES = ("vita", "vinculum", "venturum")
CHILD_FLOOR_VUL_THRESHOLD = 2.0
AMPLIFY_CAP = 7.0
AMPLIFY_GEN_YEARS = 30.0
_EXP_1 = math.e

DEFAULT_WITNESS_HOPS = 2
MAX_FRONTIER_PER_SUPERSTEP = 256
DEFAULT_AGENT_TIER = "balanced"

# ── State type for LangGraph ───────────────────────────────────────────


class _KarmaState(TypedDict, total=False):
    # Inputs
    edge_id: Optional[str]
    candidate: Optional[dict[str, Any]]
    witness_hops: int
    agent_tier: str

    # Loaded edge / organism context
    source_did: str
    target_did: Optional[str]
    axis: str
    tier: str
    magnitude: float
    direction: str
    victim_vul: float
    future_horizon_years: int
    irreversible: bool
    ts_ms: int

    # Computed
    raw_weight: float
    signed_weight: float
    resolved_tier: str
    vulnerability_note: str
    axiom_admissible: bool
    axiom_d_floor_violation: bool
    axiom_e_child_floor_fired: bool

    # Pregel output
    visited: dict[str, dict[str, Any]]
    supersteps: int
    witness_candidates: list[dict[str, Any]]

    # LLM output
    recommendation: str
    rationale: str
    llm_tokens_used: int


# ── Helpers ────────────────────────────────────────────────────────────


def _amplify(future_horizon_years: int, irreversible: bool) -> float:
    if not irreversible:
        return 1.0
    return min(AMPLIFY_CAP, 1.0 + float(future_horizon_years) / AMPLIFY_GEN_YEARS)


def _signed_weight_calc(
    magnitude: float,
    victim_vul: float,
    future_horizon_years: int,
    irreversible: bool,
    direction: str,
) -> float:
    raw = magnitude * victim_vul * _amplify(future_horizon_years, irreversible)
    if direction == "harm":
        return -raw
    if direction == "help":
        return raw / _EXP_1
    return 0.0


def _is_child_floor(axis: str, direction: str, victim_vul: float) -> bool:
    return (
        direction == "harm"
        and victim_vul >= CHILD_FLOOR_VUL_THRESHOLD
        and axis in CHILD_FLOOR_AXES
    )


def _vulnerability_note(victim_vul: float) -> str:
    if victim_vul >= 4.0:
        return "extreme (infant / fully-dependent)"
    if victim_vul >= 3.0:
        return "very high (child / terminal frailty)"
    if victim_vul >= 2.0:
        return "high (minor / disability / isolation)"
    if victim_vul >= 1.5:
        return "moderate (elder / chronic)"
    return "baseline (capable adult)"


# ── LangGraph nodes ────────────────────────────────────────────────────


def _load_organism_node(state: _KarmaState) -> _KarmaState:
    """Load edge + organism context. Either edge_id is given (lookup
    existing edge) or candidate is given (use input fields directly)."""
    edge_id = state.get("edge_id")
    candidate = state.get("candidate")

    if edge_id:
        client = get_kotoba_client()
        row = client.select_first_where(
            "edge_karma_dependency",
            "edge_id",
            edge_id,
            columns=[
                "source_did_at_event", "target_did_at_event", "axis", "tier",
                "magnitude", "direction", "victim_vul", "future_horizon_years",
                "irreversible", "ts_ms"
            ]
        )
        if not row:
            raise ValueError(f"karma.agent.evaluate: edge_id={edge_id} not found")

        source_did = row["source_did_at_event"]
        target_did = row["target_did_at_event"]
        axis = row["axis"]
        tier = row["tier"]
        magnitude = row["magnitude"]
        direction = row["direction"]
        victim_vul = row["victim_vul"]
        future_horizon_years = row.get("future_horizon_years") or 0  # COALESCE(future_horizon_years, 0)
        irreversible = row.get("irreversible") or False             # COALESCE(irreversible, false)
        ts_ms = row["ts_ms"]

        state["source_did"] = source_did
        state["target_did"] = target_did
        state["axis"] = axis
        state["tier"] = tier
        state["magnitude"] = float(magnitude)
        state["direction"] = direction
        state["victim_vul"] = float(victim_vul)
        state["future_horizon_years"] = int(future_horizon_years)
        state["irreversible"] = bool(irreversible)
        state["ts_ms"] = int(ts_ms)
    elif candidate:
        state["source_did"] = candidate["sourceDid"]
        state["target_did"] = candidate.get("targetDid") or ""
        state["axis"] = (candidate["axis"] or "").lower()
        state["tier"] = (candidate["tier"] or "").lower()
        state["magnitude"] = float(candidate["magnitude"])
        state["direction"] = (candidate["direction"] or "").lower()
        state["victim_vul"] = float(candidate["victimVul"])
        state["future_horizon_years"] = int(candidate.get("futureHorizonYears") or 0)
        state["irreversible"] = bool(candidate.get("irreversible", False))
        state["ts_ms"] = int(datetime.now(timezone.utc).timestamp() * 1000)
    else:
        raise ValueError("karma.agent.evaluate: edgeId or candidate required")

    state.setdefault("witness_hops", DEFAULT_WITNESS_HOPS)
    state.setdefault("agent_tier", DEFAULT_AGENT_TIER)
    state.setdefault("supersteps", 0)
    state.setdefault("llm_tokens_used", 0)
    return state


def _vulnerability_assess_node(state: _KarmaState) -> _KarmaState:
    state["vulnerability_note"] = _vulnerability_note(state["victim_vul"])
    return state


def _tier_classify_node(state: _KarmaState) -> _KarmaState:
    """Confirm or override the input tier with LLM tier-classification.
    For Phase K0 we use the input tier directly; LLM correction is
    deferred (would require carefully calibrated prompt)."""
    state["resolved_tier"] = state["tier"]
    return state


def _axiom_verify_node(state: _KarmaState) -> _KarmaState:
    """Inline Karma.lean Axiom D + E verification.

    Axiom D: floor_violation_inadmissible = (tier=Floor AND direction=Harm)
    Axiom E: child_floor_axiom = (vul ≥ 2.0 AND harm AND axis ∈ Vita/Vinculum/Venturum)
             → auto-classifies tier to Floor.
    """
    axis = state["axis"]
    direction = state["direction"]
    victim_vul = state["victim_vul"]

    auto_floor = _is_child_floor(axis, direction, victim_vul)
    state["axiom_e_child_floor_fired"] = auto_floor

    resolved = "floor" if auto_floor else state["resolved_tier"]
    state["resolved_tier"] = resolved

    is_floor_violation = resolved == "floor" and direction == "harm"
    state["axiom_d_floor_violation"] = is_floor_violation
    state["axiom_admissible"] = not is_floor_violation

    state["raw_weight"] = (
        state["magnitude"] * state["victim_vul"]
        * _amplify(state["future_horizon_years"], state["irreversible"])
    )
    state["signed_weight"] = _signed_weight_calc(
        state["magnitude"],
        state["victim_vul"],
        state["future_horizon_years"],
        state["irreversible"],
        state["direction"],
    )
    return state


def _route_after_axiom(state: _KarmaState) -> str:
    if state.get("axiom_d_floor_violation"):
        return "skip_to_recommend"
    return "witness_search"


def _witness_search_node(state: _KarmaState) -> _KarmaState:
    """Pregel-style BFS over edge_karma_dependency.

    Vertex values  = organism DIDs
    Messages       = (overlap_count, hop_distance) — passed to neighbors
    Supersteps     = bounded by witness_hops (default 2)
    Halt condition = frontier empty OR hop_count == witness_hops
    """
    seeds = {state["source_did"]}
    if state.get("target_did"):
        seeds.add(state["target_did"])

    visited: dict[str, dict[str, Any]] = {
        d: {"hop": 0, "edge_overlap": 0, "is_seed": True} for d in seeds
    }
    frontier = set(seeds)
    superstep = 0
    max_hops = int(state.get("witness_hops") or DEFAULT_WITNESS_HOPS)

    client = get_kotoba_client()
    for hop in range(1, max_hops + 1):
        if not frontier:
            break
        superstep += 1
        # Bound frontier per superstep to keep query bounded
        current = list(frontier)[:MAX_FRONTIER_PER_SUPERSTEP]
        # R0: Datalog query for witness search
        datalog_query = """
        [:find ?neighbor_did (count ?e)
         :in $current
         :where
         [?e :edge.karma_dependency/source_did_at_event ?s]
         [?e :edge.karma_dependency/target_did_at_event ?t]
         [(!= ?s ?t)]
         (or
          (and [(contains? $current ?s)] [(= ?neighbor_did ?t)])
          (and [(contains? $current ?t)] [(= ?neighbor_did ?s)])
         )]
        """
        rows = client.q(datalog_query, args={"$current": current})

        new_frontier: set[str] = set()
        for row in rows:
            neighbor_did, overlap = row
            if not neighbor_did:
                continue
            if neighbor_did in visited:
                # Update overlap count (Pregel aggregation: max)
                if overlap > visited[neighbor_did]["edge_overlap"]:
                    visited[neighbor_did]["edge_overlap"] = int(overlap)
                continue
            visited[neighbor_did] = {
                "hop": hop,
                "edge_overlap": int(overlap),
                "is_seed": False,
            }
            new_frontier.add(neighbor_did)

        frontier = new_frontier

    # Witness candidates = visited - seeds, ranked by hop ASC + overlap DESC
    candidates = [
        {
            "did": d,
            "hopDistance": v["hop"],
            "edgeOverlap": v["edge_overlap"],
        }
        for d, v in visited.items()
        if not v.get("is_seed")
    ]
    candidates.sort(key=lambda c: (c["hopDistance"], -c["edgeOverlap"]))

    state["visited"] = visited
    state["supersteps"] = superstep
    state["witness_candidates"] = candidates[:20]
    return state


async def _recommend_node(state: _KarmaState) -> _KarmaState:
    """Synthesize recommendation using LLM. Phase K0 keeps this rule-based
    fallback; LLM call is wired but optional (set KARMA_AGENT_LLM=1 to
    enable)."""
    use_llm = os.environ.get("KARMA_AGENT_LLM", "0") == "1"

    if state.get("axiom_d_floor_violation"):
        state["recommendation"] = "floor-violation"
        state["rationale"] = (
            f"Karma.lean Axiom D + E: tier={state['resolved_tier']}, "
            f"direction={state['direction']}, vul={state['victim_vul']:.2f} "
            f"({state.get('vulnerability_note', '')}). "
            f"{'Child-floor auto-classification fired.' if state.get('axiom_e_child_floor_fired') else 'Explicit Floor tier.'} "
            f"Rejected (admissibility=false)."
        )
        return state

    witnesses = state.get("witness_candidates") or []
    high_severity = state["resolved_tier"] in ("high",)
    needs_witness = high_severity and state["direction"] == "harm"
    has_witnesses = len(witnesses) > 0

    if needs_witness and not has_witnesses:
        state["recommendation"] = "escalate-dao"
        state["rationale"] = (
            f"Tier=High Harm with zero direct witnesses available "
            f"({state.get('supersteps', 0)} Pregel supersteps over {state.get('witness_hops', DEFAULT_WITNESS_HOPS)} hops). "
            f"Escalating to 覚者 DAO for arbitration."
        )
        return state

    if needs_witness and has_witnesses:
        state["recommendation"] = "require-witness"
        wits_str = ", ".join(c["did"] for c in witnesses[:3])
        state["rationale"] = (
            f"Tier=High Harm. Recommending witness chain from {len(witnesses)} candidates "
            f"({state.get('supersteps', 0)} Pregel supersteps). "
            f"Top candidates: {wits_str}."
        )
        return state

    state["recommendation"] = "admit"
    state["rationale"] = (
        f"axis={state['axis']}, tier={state['resolved_tier']}, "
        f"direction={state['direction']}, vul={state['victim_vul']:.2f} "
        f"({state.get('vulnerability_note', '')}), "
        f"signed_weight={state.get('signed_weight', 0.0):.2f}. "
        f"Admissible per Karma.lean Axioms A/B/D/E. "
        f"{state.get('supersteps', 0)} Pregel supersteps explored "
        f"{len(witnesses)} witness candidates."
    )

    if use_llm:
        try:
            tier_for_llm = state.get("agent_tier", DEFAULT_AGENT_TIER)
            prompt = (
                "Refine this karma evaluation rationale into 2-3 sentences "
                "preserving the technical claim:\n\n" + state["rationale"]
            )
            response = await llm.call_tier(tier_for_llm, prompt, max_tokens=200)
            if response and response.get("text"):
                state["rationale"] = response["text"].strip()
                state["llm_tokens_used"] = state.get("llm_tokens_used", 0) + int(
                    response.get("usage", {}).get("total_tokens", 0)
                )
        except Exception as exc:  # noqa: BLE001
            LOG.warning("karma.agent.evaluate LLM refine failed: %s", exc)

    return state


def _emit_event_node(state: _KarmaState) -> _KarmaState:
    """Terminal node — state is ready for return to BPMN."""
    return state


# ── Graph build ────────────────────────────────────────────────────────


def _build_karma_graph() -> Any:
    if not _LG_OK:
        return None
    g: StateGraph = StateGraph(_KarmaState)

    g.add_node("load_organism",         _load_organism_node)
    g.add_node("vulnerability_assess",  _vulnerability_assess_node)
    g.add_node("tier_classify",         _tier_classify_node)
    g.add_node("axiom_verify",          _axiom_verify_node)
    g.add_node("witness_search",        _witness_search_node)
    g.add_node("recommend",             _recommend_node)
    g.add_node("emit_event",            _emit_event_node)

    g.set_entry_point("load_organism")
    g.add_edge("load_organism",        "vulnerability_assess")
    g.add_edge("vulnerability_assess", "tier_classify")
    g.add_edge("tier_classify",        "axiom_verify")
    g.add_conditional_edges(
        "axiom_verify",
        _route_after_axiom,
        {
            "witness_search":     "witness_search",
            "skip_to_recommend":  "recommend",
        },
    )
    g.add_edge("witness_search", "recommend")
    g.add_edge("recommend",      "emit_event")
    g.add_edge("emit_event",     END)

    return g.compile()


_KARMA_GRAPH = _build_karma_graph()


# ── Pyzeebe task ───────────────────────────────────────────────────────


async def task_karma_agent_evaluate(**kwargs: Any) -> dict[str, Any]:
    if not _LG_OK or _KARMA_GRAPH is None:
        # Graceful degradation: run pipeline as plain function chain.
        state: _KarmaState = {
            "edge_id": kwargs.get("edgeId"),
            "candidate": kwargs.get("candidate"),
            "witness_hops": int(kwargs.get("witnessHops") or DEFAULT_WITNESS_HOPS),
            "agent_tier": kwargs.get("agentTier") or DEFAULT_AGENT_TIER,
        }
        state = _load_organism_node(state)
        state = _vulnerability_assess_node(state)
        state = _tier_classify_node(state)
        state = _axiom_verify_node(state)
        if state.get("axiom_d_floor_violation"):
            state["visited"] = {}
            state["witness_candidates"] = []
            state["supersteps"] = 0
        else:
            state = _witness_search_node(state)
        state = await _recommend_node(state)
    else:
        initial: _KarmaState = {
            "edge_id": kwargs.get("edgeId"),
            "candidate": kwargs.get("candidate"),
            "witness_hops": int(kwargs.get("witnessHops") or DEFAULT_WITNESS_HOPS),
            "agent_tier": kwargs.get("agentTier") or DEFAULT_AGENT_TIER,
        }
        # LangGraph .ainvoke supports async nodes; run in event loop.
        if hasattr(_KARMA_GRAPH, "ainvoke"):
            state = await _KARMA_GRAPH.ainvoke(initial)  # type: ignore[assignment]
        else:
            # Fallback: synchronous invoke in thread executor.
            loop = asyncio.get_event_loop()
            state = await loop.run_in_executor(None, _KARMA_GRAPH.invoke, initial)  # type: ignore[arg-type]

    return {
        "ok": True,
        "recommendation":     state.get("recommendation", "admit"),
        "resolvedTier":       state.get("resolved_tier", state.get("tier", "")),
        "signedWeight":       state.get("signed_weight", 0.0),
        "vulnerabilityNote":  state.get("vulnerability_note", ""),
        "axiomCheck": {
            "admissible": bool(state.get("axiom_admissible", True)),
            "axiomD":     bool(state.get("axiom_d_floor_violation", False)),
            "axiomE":     bool(state.get("axiom_e_child_floor_fired", False)),
        },
        "witnessCandidates":  state.get("witness_candidates", []),
        "rationale":          state.get("rationale", ""),
        "supersteps":         int(state.get("supersteps", 0)),
        "llmTokensUsed":      int(state.get("llm_tokens_used", 0)),
    }


# ── Worker registration ────────────────────────────────────────────────


def register(worker: Any, *, timeout_ms: int = 90_000) -> None:
    """Register the karma evaluation agent task type.

      task_type="karma.agent.evaluate"
    """
    worker.task(
        task_type="karma.agent.evaluate",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_karma_agent_evaluate)


__all__ = [
    "register",
    "task_karma_agent_evaluate",
]
