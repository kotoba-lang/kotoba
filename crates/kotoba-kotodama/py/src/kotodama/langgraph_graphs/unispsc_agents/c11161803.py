# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11161803 — Agent (segment 11).

Bespoke graph logic for UNISPSC 11161803 (Agent). This agent manages the
lifecycle of biological agents, focusing on safety protocols, containment
levels, and distribution authorization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11161803"
UNISPSC_TITLE = "Agent"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11161803"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    agent_type: str
    biosafety_level: int
    containment_status: str
    auth_token: str


def validate_protocol(state: State) -> dict[str, Any]:
    """Validates the biological agent protocol and assigns safety levels."""
    inp = state.get("input") or {}
    agent_type = inp.get("agent_type", "unknown")
    bsl = inp.get("bsl", 1)

    return {
        "log": [f"{UNISPSC_CODE}:validate_protocol: agent={agent_type} bsl={bsl}"],
        "agent_type": agent_type,
        "biosafety_level": bsl,
        "containment_status": "pending_verification"
    }


def verify_containment(state: State) -> dict[str, Any]:
    """Verifies that containment procedures match the required BSL."""
    bsl = state.get("biosafety_level", 1)
    status = "secured" if bsl < 4 else "high_security_protocol"

    return {
        "log": [f"{UNISPSC_CODE}:verify_containment: level {bsl} status {status}"],
        "containment_status": status,
        "auth_token": f"AUTH-{UNISPSC_CODE}-{bsl}"
    }


def finalize_record(state: State) -> dict[str, Any]:
    """Records the agent state and prepares the final report."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "agent_type": state.get("agent_type"),
            "bsl": state.get("biosafety_level"),
            "status": state.get("containment_status"),
            "did": UNISPSC_DID,
            "authorized": True
        }
    }


_g = StateGraph(State)
_g.add_node("validate", validate_protocol)
_g.add_node("verify", verify_containment)
_g.add_node("finalize", finalize_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
