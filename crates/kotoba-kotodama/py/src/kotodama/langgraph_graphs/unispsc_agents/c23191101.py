# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23191101 — Robot Procurement (segment 23).
Bespoke logic for industrial and service robot acquisition workflows.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23191101"
UNISPSC_TITLE = "Robot Procurement"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23191101"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    specs_validated: bool
    budget_threshold: float
    vendor_selection: str
    compliance_status: str


def validate_robot_specs(state: State) -> dict[str, Any]:
    """Validates technical requirements and payload specifications for robot procurement."""
    inp = state.get("input") or {}
    requirements = inp.get("requirements", {})
    budget = inp.get("budget", 0.0)

    # Business logic: ensure requirements are specified and budget is allocated
    is_valid = len(requirements) > 0 and budget > 1000.0

    return {
        "log": [f"{UNISPSC_CODE}:validate_robot_specs"],
        "specs_validated": is_valid,
        "budget_threshold": budget,
        "compliance_status": "PENDING"
    }


def select_robotic_vendor(state: State) -> dict[str, Any]:
    """Identifies and selects an authorized robotics vendor based on validated specs."""
    if not state.get("specs_validated"):
        return {
            "log": [f"{UNISPSC_CODE}:select_robotic_vendor_aborted"],
            "compliance_status": "FAILED_SPECS"
        }

    # Mock vendor selection from a qualified list
    selected_vendor = "Cyberdyne-Systems-Global"

    return {
        "log": [f"{UNISPSC_CODE}:select_robotic_vendor"],
        "vendor_selection": selected_vendor,
        "compliance_status": "VENDOR_MATCHED"
    }


def authorize_procurement(state: State) -> dict[str, Any]:
    """Generates the final procurement authorization and result payload."""
    vendor = state.get("vendor_selection", "None")
    status = state.get("compliance_status", "UNKNOWN")
    success = status == "VENDOR_MATCHED"

    return {
        "log": [f"{UNISPSC_CODE}:authorize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "authorized_vendor": vendor,
            "status": "APPROVED" if success else "REJECTED",
            "metadata": {
                "budget_allocated": state.get("budget_threshold"),
                "compliance_check": status
            }
        }
    }


_g = StateGraph(State)

_g.add_node("validate_specs", validate_robot_specs)
_g.add_node("select_vendor", select_robotic_vendor)
_g.add_node("authorize", authorize_procurement)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "select_vendor")
_g.add_edge("select_vendor", "authorize")
_g.add_edge("authorize", END)

graph = _g.compile()
