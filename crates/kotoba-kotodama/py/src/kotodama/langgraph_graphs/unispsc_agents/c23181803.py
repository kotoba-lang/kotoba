# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Bespoke LangGraph agent for Robot Procurement (UNISPSC 23181803).

This agent orchestrates the technical validation, vendor vetting, and
procurement authorization process for industrial and service robots.
It ensures that technical specifications meet safety and operational
standards before initiating vendor selection.
"""

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23181803"
UNISPSC_TITLE = "Robot Procurement"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23181803"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Robot Procurement
    specs_compliant: bool
    selected_vendor: str
    safety_certification_id: str
    procurement_phase: str


def evaluate_robot_specs(state: State) -> dict[str, Any]:
    """Analyzes payload, reach, and DOF requirements for the robot."""
    inp = state.get("input") or {}
    # Simulate technical requirement validation (e.g., payload must be specified)
    payload = inp.get("payload_kg", 0)
    is_compliant = payload > 0
    return {
        "log": [f"{UNISPSC_CODE}:evaluate_robot_specs"],
        "specs_compliant": is_compliant,
        "procurement_phase": "technical_evaluation"
    }


def vet_robotics_vendors(state: State) -> dict[str, Any]:
    """Screens vendors based on technical compliance and track record."""
    is_compliant = state.get("specs_compliant", False)
    # Simulate vendor selection logic
    vendor = "Universal-Bot-Dynamics" if is_compliant else "None"
    return {
        "log": [f"{UNISPSC_CODE}:vet_robotics_vendors"],
        "selected_vendor": vendor,
        "safety_certification_id": "ISO-10218-1" if is_compliant else "PENDING",
        "procurement_phase": "vendor_vetting"
    }


def authorize_robot_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement order with the selected vendor."""
    vendor = state.get("selected_vendor")
    is_valid = vendor and vendor != "None"
    return {
        "log": [f"{UNISPSC_CODE}:authorize_robot_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "status": "AUTHORIZED" if is_valid else "REJECTED",
            "vendor": vendor,
            "safety_certification": state.get("safety_certification_id"),
            "did": UNISPSC_DID,
            "ok": is_valid,
        },
        "procurement_phase": "completed"
    }


_g = StateGraph(State)

_g.add_node("evaluate_specs", evaluate_robot_specs)
_g.add_node("vet_vendors", vet_robotics_vendors)
_g.add_node("authorize_procurement", authorize_robot_procurement)

_g.add_edge(START, "evaluate_specs")
_g.add_edge("evaluate_specs", "vet_vendors")
_g.add_edge("vet_vendors", "authorize_procurement")
_g.add_edge("authorize_procurement", END)

graph = _g.compile()
