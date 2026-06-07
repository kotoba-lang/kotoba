# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101738 — Intake (segment 26).
Generator intake system validation and performance modeling.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101738"
UNISPSC_TITLE = "Intake"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101738"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Bespoke intake state for power generation machinery
    intake_category: str
    target_rpm: int
    cfm_rating: float
    bypass_enabled: bool


def validate_intake_specs(state: State) -> dict[str, Any]:
    """Parse input specs for power generator intake manifolds or ports."""
    inp = state.get("input") or {}
    category = inp.get("category", "industrial_air")
    rpm = inp.get("target_rpm", 1800)

    return {
        "log": [f"{UNISPSC_CODE}:validate_intake_specs"],
        "intake_category": category,
        "target_rpm": rpm,
    }


def compute_air_requirements(state: State) -> dict[str, Any]:
    """Compute required CFM (Cubic Feet per Minute) based on RPM and intake category."""
    rpm = state.get("target_rpm", 0)
    category = state.get("intake_category", "")

    # Simulation logic: Industrial grade requires higher volume multipliers
    multiplier = 1.25 if "industrial" in category else 1.0
    calculated_cfm = (rpm * 0.48) * multiplier

    return {
        "log": [f"{UNISPSC_CODE}:compute_air_requirements"],
        "cfm_rating": calculated_cfm,
        "bypass_enabled": calculated_cfm > 1200,
    }


def emit_intake_report(state: State) -> dict[str, Any]:
    """Finalize the intake configuration data and compliance status."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_intake_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "configuration": {
                "category": state.get("intake_category"),
                "cfm_requirement": state.get("cfm_rating"),
                "rpm_sync": state.get("target_rpm"),
                "auxiliary_bypass": state.get("bypass_enabled"),
            },
            "validation_status": "certified" if state.get("cfm_rating", 0) > 0 else "failed",
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_intake_specs)
_g.add_node("compute", compute_air_requirements)
_g.add_node("emit", emit_intake_report)

_g.add_edge(START, "validate")
_g.add_edge("validate", "compute")
_g.add_edge("compute", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
