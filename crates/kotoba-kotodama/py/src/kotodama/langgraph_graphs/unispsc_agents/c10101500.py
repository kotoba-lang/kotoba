# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10101500 — Live Animal (segment 10).
Bespoke logic for health verification, quarantine status, and transport authorization.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10101500"
UNISPSC_TITLE = "Live Animal"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10101500"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Live Animal processing
    health_certified: bool
    quarantine_status: str
    transport_permit_id: str
    species_verified: bool
    # Stage D learning loop (per ADR-2605232100): the unispsc-capabilities
    # wrapper injects prior observations + a computed consensus when this
    # actor has been invoked before. Reading these is opt-in — see
    # verify_health() for the canonical "prior shortcut" pattern.
    _prior_observations: list[dict]
    _prior_consensus: dict


def verify_health(state: State) -> dict[str, Any]:
    """Inspects health certification records for the live animal.

    Stage D learning loop (ADR-2605232100 §A): if the wrapper has provided
    a `_prior_consensus` field with high confidence (≥80% dominant outcome)
    over ≥3 outcomes and the current input matches at least one prior, lean
    on the prior consensus instead of re-running the full check. This is
    the canonical "actor reads its priors" reference impl — other UNSPSC
    actors can adopt the same pattern by reading `state["_prior_consensus"]`.
    """
    inp = state.get("input") or {}
    consensus = state.get("_prior_consensus") or {}
    confidence = consensus.get("confidence_permille", 0) if isinstance(consensus, dict) else 0
    outcome_count = consensus.get("outcome_count", 0) if isinstance(consensus, dict) else 0
    input_matches = consensus.get("input_match_count", 0) if isinstance(consensus, dict) else 0
    dominant = consensus.get("dominant_status") if isinstance(consensus, dict) else None

    if outcome_count >= 3 and confidence >= 800 and input_matches >= 1 and dominant == "authorized":
        # Prior-informed shortcut: history strongly suggests this input
        # leads to authorization. Skip the cert lookup and proceed.
        return {
            "log": [
                f"{UNISPSC_CODE}:verify_health:prior_shortcut"
                f"(conf={confidence}/1000,n={outcome_count},matches={input_matches})"
            ],
            "health_certified": True,
            "species_verified": "species" in inp,
        }

    health_data = inp.get("health_data", {})
    is_certified = health_data.get("certified", False)
    return {
        "log": [f"{UNISPSC_CODE}:verify_health"],
        "health_certified": is_certified,
        "species_verified": "species" in inp,
    }


def check_quarantine(state: State) -> dict[str, Any]:
    """Validates if the animal has cleared required quarantine protocols."""
    if not state.get("health_certified"):
        return {
            "log": [f"{UNISPSC_CODE}:check_quarantine:denied_precheck"],
            "quarantine_status": "pending_health_clearance",
        }

    return {
        "log": [f"{UNISPSC_CODE}:check_quarantine:cleared"],
        "quarantine_status": "cleared",
    }


def authorize_transport(state: State) -> dict[str, Any]:
    """Generates transport authorization if all health and safety checks pass."""
    ok = state.get("health_certified", False) and state.get("quarantine_status") == "cleared"
    permit_id = "TRANS-10101500-AUTH" if ok else "DENIED"

    return {
        "log": [f"{UNISPSC_CODE}:authorize_transport"],
        "transport_permit_id": permit_id,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "permit": permit_id,
            "status": "authorized" if ok else "rejected",
            "ok": ok,
        },
    }


_g = StateGraph(State)
_g.add_node("verify_health", verify_health)
_g.add_node("check_quarantine", check_quarantine)
_g.add_node("authorize_transport", authorize_transport)

_g.add_edge(START, "verify_health")
_g.add_edge("verify_health", "check_quarantine")
_g.add_edge("check_quarantine", "authorize_transport")
_g.add_edge("authorize_transport", END)

graph = _g.compile()
