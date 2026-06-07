# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20142901 — Well stimulation and completions equipment (segment 20).

Bespoke logic for managing well completion workflows, including pressure
validation and stimulation load calculation for deep-well operations.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20142901"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20142901"


class State(TypedDict, total=False):
    # Required fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific fields for Well Stimulation & Completions
    well_id: str
    target_pressure_psi: float
    casing_integrity_verified: bool
    fluid_volume_liters: float
    completion_method: str


def validate_well_parameters(state: State) -> dict[str, Any]:
    """Validates the input parameters for well stimulation safety."""
    inp = state.get("input") or {}
    well_id = inp.get("well_id", "UNKNOWN-01")
    pressure = float(inp.get("target_pressure", 5000.0))

    # Simple safety threshold check
    safe = pressure < 15000.0

    return {
        "log": [f"{UNISPSC_CODE}:validate_well_parameters: well_id={well_id}"],
        "well_id": well_id,
        "target_pressure_psi": pressure,
        "casing_integrity_verified": safe,
        "completion_method": inp.get("method", "Hydraulic Fracturing")
    }


def calculate_stimulation_load(state: State) -> dict[str, Any]:
    """Calculates required fluid volumes based on pressure targets."""
    pressure = state.get("target_pressure_psi", 0.0)
    # Heuristic: 100 liters per 10 PSI target
    volume = (pressure / 10.0) * 100.0

    return {
        "log": [f"{UNISPSC_CODE}:calculate_stimulation_load: volume={volume}L"],
        "fluid_volume_liters": volume
    }


def finalize_completion_plan(state: State) -> dict[str, Any]:
    """Generates the final engineering result for the completions equipment."""
    well_id = state.get("well_id")
    verified = state.get("casing_integrity_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_completion_plan: status={'READY' if verified else 'ABORT'}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "well_id": well_id,
            "operational_status": "APPROVED" if verified else "SAFETY_HOLD",
            "required_volume": state.get("fluid_volume_liters"),
            "method": state.get("completion_method"),
            "ok": verified,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_well_parameters)
_g.add_node("calculate", calculate_stimulation_load)
_g.add_node("finalize", finalize_completion_plan)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calculate")
_g.add_edge("calculate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
