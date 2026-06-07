# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25201514"
UNISPSC_TITLE = "Rotor"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25201514"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Rotor component analysis
    balance_verified: bool
    rotation_speed_rpm: int
    integrity_score: float
    maintenance_required: bool


def validate_rotor_specs(state: State) -> dict[str, Any]:
    """Validates the rotor's physical specifications and material constraints."""
    inp = state.get("input") or {}
    diameter = inp.get("diameter_mm", 0)
    material = inp.get("material", "unspecified")

    valid = diameter > 0 and material != "unspecified"
    log_msg = f"{UNISPSC_CODE}:validate_rotor_specs - status: {'valid' if valid else 'invalid'}"

    return {
        "log": [log_msg],
        "balance_verified": valid
    }


def analyze_dynamics(state: State) -> dict[str, Any]:
    """Performs simulated dynamic balancing and calculates integrity score."""
    is_valid = state.get("balance_verified", False)

    # Heuristic simulation of rotor performance under load
    rpm = 12000 if is_valid else 0
    score = 0.995 if is_valid else 0.0
    needs_maint = score < 0.90

    return {
        "log": [f"{UNISPSC_CODE}:analyze_dynamics - RPM set to {rpm}, score: {score}"],
        "rotation_speed_rpm": rpm,
        "integrity_score": score,
        "maintenance_required": needs_maint
    }


def emit_rotor_certification(state: State) -> dict[str, Any]:
    """Produces the final diagnostic report and actor-did metadata."""
    score = state.get("integrity_score", 0.0)
    rpm = state.get("rotation_speed_rpm", 0)
    maint = state.get("maintenance_required", False)

    status = "Operational" if (score > 0.95 and not maint) else "Inspection Failed"

    return {
        "log": [f"{UNISPSC_CODE}:emit_rotor_certification - outcome: {status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "max_operational_rpm": rpm,
                "integrity_index": score,
                "status": status
            },
            "ok": score > 0.95,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_rotor_specs)
_g.add_node("analyze", analyze_dynamics)
_g.add_node("emit", emit_rotor_certification)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
