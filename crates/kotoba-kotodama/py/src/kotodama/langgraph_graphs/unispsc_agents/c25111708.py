# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111708"
UNISPSC_TITLE = "Boat Procurement"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111708"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    vessel_specs: dict[str, Any]
    maritime_compliance: bool
    vendor_selection: str
    procurement_phase: str


def validate_vessel_requirements(state: State) -> dict[str, Any]:
    """Extracts and validates boat specifications from input."""
    inp = state.get("input") or {}
    specs = {
        "hull_type": inp.get("hull_type", "standard"),
        "length_m": inp.get("length_m", 0.0),
        "engine_rating": inp.get("engine_rating", "N/A"),
    }
    return {
        "log": [f"{UNISPSC_CODE}:validate_vessel_requirements"],
        "vessel_specs": specs,
        "procurement_phase": "specification_validated",
    }


def verify_maritime_compliance(state: State) -> dict[str, Any]:
    """Checks specs against maritime safety and regulatory standards."""
    specs = state.get("vessel_specs", {})
    # Simple logic: boats over 5m with an engine rating are compliant for this agent
    is_compliant = specs.get("length_m", 0) > 5.0 and specs.get("engine_rating") != "N/A"
    return {
        "log": [f"{UNISPSC_CODE}:verify_maritime_compliance:status={is_compliant}"],
        "maritime_compliance": is_compliant,
        "procurement_phase": "compliance_audited",
    }


def issue_procurement_order(state: State) -> dict[str, Any]:
    """Finalizes the procurement order if compliance is met."""
    compliant = state.get("maritime_compliance", False)
    vendor = "MARITIME-GLOBAL-VENDOR-001" if compliant else "NONE"

    return {
        "log": [f"{UNISPSC_CODE}:issue_procurement_order"],
        "vendor_selection": vendor,
        "procurement_phase": "completed",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "order_status": "authorized" if compliant else "rejected",
            "vendor": vendor,
            "ok": compliant,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_requirements", validate_vessel_requirements)
_g.add_node("verify_compliance", verify_maritime_compliance)
_g.add_node("issue_order", issue_procurement_order)

_g.add_edge(START, "validate_requirements")
_g.add_edge("validate_requirements", "verify_compliance")
_g.add_edge("verify_compliance", "issue_order")
_g.add_edge("issue_order", END)

graph = _g.compile()
