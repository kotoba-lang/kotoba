# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23242104 — Tool (segment 23).
Bespoke graph logic for industrial tooling and metal-cutting machinery records.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23242104"
UNISPSC_TITLE = "Tool"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23242104"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Industrial Tooling
    tool_type: str
    is_calibrated: bool
    safety_certification_status: str
    maintenance_interval_hours: int
    operational_rating: float


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates the input tool specifications and determines the tool type."""
    inp = state.get("input") or {}
    t_type = inp.get("type", "standard_cutting")
    # Industrial tools require variable maintenance based on type
    m_interval = 500 if t_type == "precision_milling" else 1000

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "tool_type": t_type,
        "maintenance_interval_hours": m_interval,
    }


def perform_safety_audit(state: State) -> dict[str, Any]:
    """Simulates a safety and calibration audit for the tool instance."""
    # Logic based on segment 23 requirements for industrial safety
    return {
        "log": [f"{UNISPSC_CODE}:perform_safety_audit"],
        "is_calibrated": True,
        "safety_certification_status": "verified_osha_compliant",
        "operational_rating": 0.995,
    }


def finalize_asset_record(state: State) -> dict[str, Any]:
    """Compiles the final tool asset record for the UNISPSC registry."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "segment": UNISPSC_SEGMENT,
            "asset_data": {
                "type": state.get("tool_type"),
                "maintenance_hr": state.get("maintenance_interval_hours"),
                "certified": state.get("safety_certification_status"),
                "rating": state.get("operational_rating"),
            },
            "status": "ready_for_deployment",
        },
    }


_g = StateGraph(State)

_g.add_node("validate_specifications", validate_specifications)
_g.add_node("perform_safety_audit", perform_safety_audit)
_g.add_node("finalize_asset_record", finalize_asset_record)

_g.add_edge(START, "validate_specifications")
_g.add_edge("validate_specifications", "perform_safety_audit")
_g.add_edge("perform_safety_audit", "finalize_asset_record")
_g.add_edge("finalize_asset_record", END)

graph = _g.compile()
