# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25191507 — Deicing (segment 25).

Bespoke logic for handling aircraft or surface deicing procedures,
including environmental assessment, fluid application, and safety verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25191507"
UNISPSC_TITLE = "Deicing"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25191507"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Deicing
    surface_temperature_celsius: float
    precipitation_type: str
    deicing_fluid_type: str
    holdover_time_minutes: int
    clearance_verified: bool


def inspect_conditions(state: State) -> dict[str, Any]:
    """Inspects environmental conditions to determine deicing requirements."""
    inp = state.get("input") or {}
    temp = inp.get("temperature", -2.5)
    precip = inp.get("precipitation", "frost")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_conditions - Temp: {temp}C, Precip: {precip}"],
        "surface_temperature_celsius": temp,
        "precipitation_type": precip,
    }


def apply_treatment(state: State) -> dict[str, Any]:
    """Calculates treatment parameters and simulates fluid application."""
    temp = state.get("surface_temperature_celsius", 0.0)
    precip = state.get("precipitation_type", "none")

    # Simple logic to select fluid type
    fluid = "Type I" if temp > -3 else "Type IV"
    hot = 45 if fluid == "Type IV" else 20

    return {
        "log": [f"{UNISPSC_CODE}:apply_treatment - Selected {fluid}"],
        "deicing_fluid_type": fluid,
        "holdover_time_minutes": hot,
    }


def verify_clearance(state: State) -> dict[str, Any]:
    """Final inspection to ensure surfaces are clear for operation."""
    hot = state.get("holdover_time_minutes", 0)
    verified = hot > 0

    return {
        "log": [f"{UNISPSC_CODE}:verify_clearance - Status: {verified}"],
        "clearance_verified": verified,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "fluid_applied": state.get("deicing_fluid_type"),
            "holdover_limit": hot,
            "ok": verified,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_conditions", inspect_conditions)
_g.add_node("apply_treatment", apply_treatment)
_g.add_node("verify_clearance", verify_clearance)

_g.add_edge(START, "inspect_conditions")
_g.add_edge("inspect_conditions", "apply_treatment")
_g.add_edge("apply_treatment", "verify_clearance")
_g.add_edge("verify_clearance", END)

graph = _g.compile()
