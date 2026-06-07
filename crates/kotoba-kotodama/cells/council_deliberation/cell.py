"""
CouncilDeliberationCell — Generic Council Lv6+ deliberation orchestrator.

Per ADR-2605192415 §2 (Tier C: Per-Decision council cells).

This is the **generic** Council deliberation cell used by:
  - CharterAttestationRequestCell (escalation)
  - LandDisputeResolutionCell (escalation)
  - StewardSuccessionCell (escalation)
  - ForceAuthorizationCell (escalation)
  - EthicsContentClassifierCell T2/T4 borderline (escalation)
  - PublicFundGrantCell (governance vote, but Council recognition separate)

Instantiated per-attestation. Lives in Tier C (Per-Decision), not Per-Domain.

Trigger: invoked by other cells (escalation pattern, not direct MST listener)
Effect:
  - Notify all Lv6+ Council members
  - Collect signed deliberation records
  - On ≥3 signatures with quorum-consistent verdict → emit attestation
  - Append to canonical attestation chain

Murakumo node: levi (orchestrator), asher (failover replica)
"""

from __future__ import annotations

from typing import Literal, TypedDict, Annotated
from operator import add

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.base import BaseCheckpointSaver


class CouncilDeliberationState(TypedDict, total=False):
    # Input — escalation request
    attestation_request_uri: str  # at:// URI of the originating request
    request_type: Literal[
        "charter-non-aligned",
        "charter-rehabilitation",
        "land-dispute",
        "steward-succession",
        "force-authorization",
        "eros-gore-boundary",
        "public-fund-recognition",
    ]
    subject_summary: str
    evidence_uris: list[str]
    llm_pre_analysis_uri: str | None  # if pre-analyzed by another cell

    # Council member states
    notified_members: list[str]  # DIDs of Lv6+ members notified
    council_votes: Annotated[list[dict], add]  # each: {member_did, vote, rationale_uri, signature}

    # Quorum
    required_quorum: int  # default 3, can be higher for high-stakes (e.g., 5 for force)
    quorum_reached: bool
    determination: Literal["approve", "reject", "request-more-evidence"]

    # Output
    attestation_uri: str
    onchain_tx_hash: str


def build_graph(
    checkpointer: BaseCheckpointSaver,
    council_notifier,  # interface to notify Lv6+ members (PDS push, email)
    onchain_attestation_port,  # writes to ChartersComplianceRegistry / LandRegistry / etc.
):
    g = StateGraph(CouncilDeliberationState)

    g.add_node("load_request", load_request)
    g.add_node("determine_quorum", determine_quorum)
    g.add_node("notify_council", lambda s: notify_council(s, council_notifier))
    g.add_node("collect_votes", collect_votes)
    g.add_node("evaluate_quorum", evaluate_quorum)
    g.add_node("emit_attestation", lambda s: emit_attestation(s, onchain_attestation_port))
    g.add_node("emit_at_record", emit_at_record)

    g.add_edge(START, "load_request")
    g.add_edge("load_request", "determine_quorum")
    g.add_edge("determine_quorum", "notify_council")
    g.add_edge("notify_council", "collect_votes")

    # Fixed-point: wait for more votes if quorum not reached
    def quorum_router(state):
        if state.get("quorum_reached"):
            return "emit_attestation"
        # Loop back to collect more — checkpointer pauses here
        return "collect_votes"

    g.add_edge("collect_votes", "evaluate_quorum")
    g.add_conditional_edges("evaluate_quorum", quorum_router)
    g.add_edge("emit_attestation", "emit_at_record")
    g.add_edge("emit_at_record", END)

    return g.compile(checkpointer=checkpointer)


# ─── Node functions ──────────────────────────────────────────────────


def load_request(state):
    """Load escalation request + linked LLM analysis (if any)."""
    return state


def determine_quorum(state):
    """Set quorum based on request_type."""
    high_stakes_types = ("force-authorization", "charter-rehabilitation")
    quorum = 5 if state.get("request_type") in high_stakes_types else 3
    return {**state, "required_quorum": quorum}


def notify_council(state, notifier):
    """Push notification to all Lv6+ Council members via PDS + email."""
    # TODO: notifier.push_to_lv6_members(state)
    return state


def collect_votes(state):
    """Fixed-point — wait for Council member votes via MST listener.

    Each Lv6+ Council member writes an com.etzhayyim.apps.etzhayyim.charter-counsel-vote
    record on their own PDS. The MST listener triggers re-entry to this node
    with the new vote appended to `council_votes` (LangGraph reducer = add).
    """
    return state


def evaluate_quorum(state):
    """Check if required quorum reached + determine majority verdict."""
    votes = state.get("council_votes", [])
    required = state.get("required_quorum", 3)

    if len(votes) < required:
        return {**state, "quorum_reached": False}

    approve_count = sum(1 for v in votes if v["vote"] == "approve")
    reject_count = sum(1 for v in votes if v["vote"] == "reject")

    if approve_count >= required:
        determination = "approve"
    elif reject_count >= required:
        determination = "reject"
    else:
        return {**state, "quorum_reached": False}  # split, wait for more

    return {**state, "quorum_reached": True, "determination": determination}


def emit_attestation(state, port):
    """Emit on-chain attestation (target depends on request_type)."""
    # TODO: route by request_type:
    #   charter-non-aligned → ChartersComplianceRegistry.attestNonAligned*()
    #   land-dispute → LandRegistry.resolveDispute()
    #   steward-succession → LandRegistry.reassignSteward()
    #   force-authorization → ForceAuthorization.recordAfterAction()
    return {**state, "onchain_tx_hash": "0x..."}


def emit_at_record(state):
    """Emit com.etzhayyim.apps.etzhayyim.charter-attestation (or type-specific) record."""
    return state
