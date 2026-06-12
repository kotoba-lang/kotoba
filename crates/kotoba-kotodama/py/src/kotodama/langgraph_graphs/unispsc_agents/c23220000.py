# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23220000 — Industrial Manufacturing Services.

Bespoke graph logic for industrial equipment maintenance and repair services
within the manufacturing segment.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23220000"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23220000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    manufacturing_line_id: str
    service_category: str
    safety_inspection_status: str
    parts_requisition_id: str


def receive_manufacturing_order(state: State) -> dict[str, Any]:
    """
    Triage incoming industrial service requests and identify the target line.
    """
    inp = state.get("input") or {}
    line_id = inp.get("line_id", "MAIN-ASSEMBLY-01")
    category = inp.get("category", "preventive_maintenance")
    return {
        "log": [f"{UNISPSC_CODE}:receive_manufacturing_order"],
        "manufacturing_line_id": line_id,
        "service_category": category,
    }


def conduct_safety_assessment(state: State) -> dict[str, Any]:
    """
    Verify safety protocols (LOTO) and stage required parts.
    """
    # In a real scenario, this would check against safety compliance databases
    return {
        "log": [f"{UNISPSC_CODE}:conduct_safety_assessment"],
        "safety_inspection_status": "PASSED",
        "parts_requisition_id": "REQ-2322-AUTO-001",
    }


def emit_service_authorization(state: State) -> dict[str, Any]:
    """
    Finalize the service plan and emit authorization for execution.
    """
    return {
        "log": [f"{UNISPSC_CODE}:emit_service_authorization"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "line_id": state.get("manufacturing_line_id"),
            "safety_status": state.get("safety_inspection_status"),
            "parts_ref": state.get("parts_requisition_id"),
            "status": "authorized",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("receive", receive_manufacturing_order)
_g.add_node("assess", conduct_safety_assessment)
_g.add_node("emit", emit_service_authorization)

_g.add_edge(START, "receive")
_g.add_edge("receive", "assess")
_g.add_edge("assess", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
