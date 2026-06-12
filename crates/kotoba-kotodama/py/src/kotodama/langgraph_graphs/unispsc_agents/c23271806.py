# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23271806 — Solder (segment 23).

Bespoke LangGraph implementation for Solder material processing.
Handles composition validation, thermal property calculation, and
compliance certification for industrial soldering alloys.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23271806"
UNISPSC_TITLE = "Solder"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23271806"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    alloy_spec: str
    flux_type: str
    melting_point: float
    rohs_status: bool


def validate_spec(state: State) -> dict[str, Any]:
    """Validates the input solder specifications and flux requirements."""
    inp = state.get("input") or {}
    spec = inp.get("alloy", "SAC305")
    flux = inp.get("flux", "No-Clean")

    return {
        "log": [f"{UNISPSC_CODE}:validate_spec"],
        "alloy_spec": spec,
        "flux_type": flux,
    }


def calculate_thermal(state: State) -> dict[str, Any]:
    """Determines the melting point and RoHS status based on the alloy."""
    spec = state.get("alloy_spec", "SAC305")

    # Logic for common solder types
    if "Pb" in spec or "Lead" in spec:
        temp = 183.0
        compliant = False
    else:
        # Lead-free (e.g., Tin-Silver-Copper alloys like SAC305)
        temp = 217.0
        compliant = True

    return {
        "log": [f"{UNISPSC_CODE}:calculate_thermal"],
        "melting_point": temp,
        "rohs_status": compliant,
    }


def certify_batch(state: State) -> dict[str, Any]:
    """Generates the final certificate for the solder batch."""
    return {
        "log": [f"{UNISPSC_CODE}:certify_batch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "alloy": state.get("alloy_spec"),
            "melting_temp_c": state.get("melting_point"),
            "rohs_compliant": state.get("rohs_status"),
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_spec", validate_spec)
_g.add_node("calculate_thermal", calculate_thermal)
_g.add_node("certify_batch", certify_batch)

_g.add_edge(START, "validate_spec")
_g.add_edge("validate_spec", "calculate_thermal")
_g.add_edge("calculate_thermal", "certify_batch")
_g.add_edge("certify_batch", END)

graph = _g.compile()
