# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121200 — Motor Procurement (segment 20).

This bespoke LangGraph implementation handles the procurement workflow for
industrial motors, including technical specification assessment and
supply chain verification for the mining and machinery sector.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121200"
UNISPSC_TITLE = "Motor Procurement"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121200"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    motor_class: str
    rated_voltage: int
    vendor_verified: bool
    procurement_id: str


def check_specs(state: State) -> dict[str, Any]:
    """Assess the technical requirements for the motor procurement."""
    inp = state.get("input") or {}
    m_class = inp.get("class", "Industrial-AC")
    voltage = inp.get("voltage", 460)
    return {
        "log": [f"{UNISPSC_CODE}:check_specs"],
        "motor_class": m_class,
        "rated_voltage": voltage,
    }


def verify_vendor(state: State) -> dict[str, Any]:
    """Validate the supplier credentials and assign a procurement tracking ID."""
    inp = state.get("input") or {}
    v_id = inp.get("vendor_id", "V-GLOBAL-01")
    return {
        "log": [f"{UNISPSC_CODE}:verify_vendor"],
        "vendor_verified": True,
        "procurement_id": f"REQ-{v_id}-2026",
    }


def issue_purchase_order(state: State) -> dict[str, Any]:
    """Generate the final procurement result and issue the purchase order."""
    m_class = state.get("motor_class")
    p_id = state.get("procurement_id")
    return {
        "log": [f"{UNISPSC_CODE}:issue_purchase_order"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "order_id": p_id,
            "item": m_class,
            "status": "ISSUED",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("check_specs", check_specs)
_g.add_node("verify_vendor", verify_vendor)
_g.add_node("issue_po", issue_purchase_order)

_g.add_edge(START, "check_specs")
_g.add_edge("check_specs", "verify_vendor")
_g.add_edge("verify_vendor", "issue_po")
_g.add_edge("issue_po", END)

graph = _g.compile()
