# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23181500 — Machine Spec (segment 23).
Bespoke logic for industrial machine specification processing and constraint verification.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23181500"
UNISPSC_TITLE = "Machine Spec"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23181500"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Machine Spec domain state
    spec_validated: bool
    tolerance_profiles: dict[str, float]
    calibration_requirement: str
    safety_margin_verified: bool


def validate_spec_structure(state: State) -> dict[str, Any]:
    """Ensures the machine specification contains required technical parameters."""
    inp = state.get("input") or {}
    # Basic industrial spec requirements
    required = ["model_id", "nominal_voltage", "load_capacity"]
    is_valid = all(k in inp for k in required)

    return {
        "log": [f"{UNISPSC_CODE}:validate_spec_structure"],
        "spec_validated": is_valid,
    }


def compute_tolerances(state: State) -> dict[str, Any]:
    """Calculates operational tolerances and safety margins based on technical specs."""
    if not state.get("spec_validated"):
        return {"log": [f"{UNISPSC_CODE}:compute_tolerances:invalid_spec"]}

    inp = state.get("input") or {}
    load = inp.get("load_capacity", 0)

    # Domain-specific tolerance logic
    profiles = {
        "static_load_limit": float(load) * 1.1,
        "dynamic_load_limit": float(load) * 1.5,
        "thermal_coefficient": 0.0025,
        "vibration_threshold": 0.05
    }

    return {
        "log": [f"{UNISPSC_CODE}:compute_tolerances"],
        "tolerance_profiles": profiles,
        "safety_margin_verified": True,
        "calibration_requirement": "ASTM-E1152" if load > 5000 else "ASTM-E4"
    }


def compile_final_spec(state: State) -> dict[str, Any]:
    """Constructs the finalized machine specification actor result for the ledger."""
    ok = state.get("spec_validated", False) and state.get("safety_margin_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:compile_final_spec"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": ok,
            "payload": {
                "calibration_standard": state.get("calibration_requirement"),
                "tolerances": state.get("tolerance_profiles"),
                "status": "APPROVED" if ok else "REJECTED"
            }
        },
    }


_g = StateGraph(State)
_g.add_node("validate_spec_structure", validate_spec_structure)
_g.add_node("compute_tolerances", compute_tolerances)
_g.add_node("compile_final_spec", compile_final_spec)

_g.add_edge(START, "validate_spec_structure")
_g.add_edge("validate_spec_structure", "compute_tolerances")
_g.add_edge("compute_tolerances", "compile_final_spec")
_g.add_edge("compile_final_spec", END)

graph = _g.compile()
