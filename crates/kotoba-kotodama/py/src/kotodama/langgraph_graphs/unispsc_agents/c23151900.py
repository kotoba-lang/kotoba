# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23151900 — Robot Procure (segment 23).

Bespoke LangGraph implementation for robot procurement workflows. This agent
handles requirement analysis, vendor sourcing, and purchase authorization
for industrial robotics systems.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23151900"
UNISPSC_TITLE = "Robot Procure"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23151900"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    robot_type: str
    safety_rating: str
    vendor_shortlist: list[str]
    budget_verified: bool


def analyze_requirements(state: State) -> dict[str, Any]:
    """Inspects input for robot specifications and safety standards."""
    inp = state.get("input") or {}
    r_type = inp.get("robot_type", "collaborative")
    return {
        "log": [f"{UNISPSC_CODE}:analyze_requirements"],
        "robot_type": r_type,
        "safety_rating": "ISO-10218-1",
    }


def source_vendors(state: State) -> dict[str, Any]:
    """Filters qualified vendors based on the identified robot type."""
    r_type = state.get("robot_type", "collaborative")
    vendors = ["Fanuc", "ABB", "KUKA"] if r_type == "industrial" else ["Universal Robots", "Rethink Robotics"]
    return {
        "log": [f"{UNISPSC_CODE}:source_vendors"],
        "vendor_shortlist": vendors,
    }


def authorize_purchase(state: State) -> dict[str, Any]:
    """Finalizes procurement selection and authorizes the purchase order."""
    vendors = state.get("vendor_shortlist", [])
    selected = vendors[0] if vendors else "N/A"
    return {
        "log": [f"{UNISPSC_CODE}:authorize_purchase"],
        "budget_verified": True,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "selected_vendor": selected,
            "robot_type": state.get("robot_type"),
            "safety_protocol": state.get("safety_rating"),
            "status": "authorized",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("analyze_requirements", analyze_requirements)
_g.add_node("source_vendors", source_vendors)
_g.add_node("authorize_purchase", authorize_purchase)

_g.add_edge(START, "analyze_requirements")
_g.add_edge("analyze_requirements", "source_vendors")
_g.add_edge("source_vendors", "authorize_purchase")
_g.add_edge("authorize_purchase", END)

graph = _g.compile()
