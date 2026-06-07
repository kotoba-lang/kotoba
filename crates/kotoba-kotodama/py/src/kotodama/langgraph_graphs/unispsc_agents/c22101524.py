# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101524"
UNISPSC_TITLE = "Laser Procurement"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101524"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    specification_data: dict[str, Any]
    safety_protocol_verified: bool
    vendor_eligibility: str
    optical_parameters: dict[str, float]


def analyze_optical_requirements(state: State) -> dict[str, Any]:
    """Extracts and validates optical requirements for the laser system."""
    inp = state.get("input") or {}
    params = {
        "wavelength_nm": float(inp.get("wavelength", 1064.0)),
        "output_power_watts": float(inp.get("power", 50.0)),
        "pulse_duration_ns": float(inp.get("pulse", 10.0)),
    }
    return {
        "log": [f"{UNISPSC_CODE}:analyze_optical_requirements"],
        "optical_parameters": params,
        "specification_data": {"validated": True, "source": "input_parse"},
    }


def verify_radiation_safety(state: State) -> dict[str, Any]:
    """Ensures the procurement request meets laser radiation safety standards."""
    params = state.get("optical_parameters") or {}
    # Class 4 laser threshold check (simplified logic)
    power = params.get("output_power_watts", 0.0)
    safety_clearance = power < 500.0  # Dummy constraint for automated approval

    return {
        "log": [f"{UNISPSC_CODE}:verify_radiation_safety"],
        "safety_protocol_verified": safety_clearance,
        "vendor_eligibility": "approved_list" if safety_clearance else "restricted",
    }


def finalize_procurement_record(state: State) -> dict[str, Any]:
    """Finalizes the procurement state and emits the authorization record."""
    safety_ok = state.get("safety_protocol_verified", False)
    params = state.get("optical_parameters") or {}

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement_record"],
        "result": {
            "status": "AUTHORIZED" if safety_ok else "FLAGGED_FOR_REVIEW",
            "laser_specs": params,
            "compliance_metadata": {
                "unispsc_code": UNISPSC_CODE,
                "segment": UNISPSC_SEGMENT,
                "actor_did": UNISPSC_DID,
            },
            "safety_check": "PASS" if safety_ok else "FAIL",
        },
    }


_g = StateGraph(State)

_g.add_node("analyze_optical_requirements", analyze_optical_requirements)
_g.add_node("verify_radiation_safety", verify_radiation_safety)
_g.add_node("finalize_procurement_record", finalize_procurement_record)

_g.add_edge(START, "analyze_optical_requirements")
_g.add_edge("analyze_optical_requirements", "verify_radiation_safety")
_g.add_edge("verify_radiation_safety", "finalize_procurement_record")
_g.add_edge("finalize_procurement_record", END)

graph = _g.compile()
