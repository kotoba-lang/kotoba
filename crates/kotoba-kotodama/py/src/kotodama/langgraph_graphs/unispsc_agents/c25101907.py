# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25101907 — Caravan (segment 25).

Bespoke graph logic for certifying Caravans based on weight distribution,
safety compliance verification, and registration certification.
"""

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25101907"
UNISPSC_TITLE = "Caravan"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25101907"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    axle_count: int
    gross_weight_kg: float
    safety_inspection_passed: bool
    chassis_id: str
    is_certified: bool


def inspect_specifications(state: State) -> dict[str, Any]:
    """Analyzes the caravan's weight and physical configuration."""
    inp = state.get("input") or {}
    weight = float(inp.get("weight_kg", 2000.0))
    axles = int(inp.get("axles", 2))
    cid = str(inp.get("chassis_id", "CV-UNKNOWN"))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specifications"],
        "gross_weight_kg": weight,
        "axle_count": axles,
        "chassis_id": cid,
    }


def verify_safety_compliance(state: State) -> dict[str, Any]:
    """Validates safety standards for towed vehicle roadworthiness."""
    weight = state.get("gross_weight_kg", 0.0)
    axles = state.get("axle_count", 1)

    # Safety heuristic: Caravans must not exceed 1600kg per axle for standard towing
    load_per_axle = weight / axles if axles > 0 else weight
    compliance = load_per_axle <= 1600.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety_compliance"],
        "safety_inspection_passed": compliance,
    }


def emit_certification(state: State) -> dict[str, Any]:
    """Generates the final certification status and result payload."""
    is_safe = state.get("safety_inspection_passed", False)

    return {
        "log": [f"{UNISPSC_CODE}:emit_certification"],
        "is_certified": is_safe,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "chassis_id": state.get("chassis_id"),
            "compliance_metrics": {
                "weight_kg": state.get("gross_weight_kg"),
                "axles": state.get("axle_count"),
            },
            "ok": is_safe,
            "certification_status": "VALID" if is_safe else "REJECTED_OVERWEIGHT",
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_specifications)
_g.add_node("verify", verify_safety_compliance)
_g.add_node("emit", emit_certification)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
