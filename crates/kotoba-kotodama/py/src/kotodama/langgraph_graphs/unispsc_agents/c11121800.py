# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11121800 — Coal Procurement (segment 11).

Bespoke graph logic for coal acquisition workflows, handling quality
specifications, tonnage requirements, and logistics constraints.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11121800"
UNISPSC_TITLE = "Coal Procurement"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11121800"


class State(TypedDict, total=False):
    # Required fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain specific fields for Coal Procurement
    tonnage: float
    calorific_value_kcal: int
    sulfur_content_pct: float
    delivery_port: str
    supplier_vetted: bool


def verify_requisition(state: State) -> dict[str, Any]:
    """Validates the initial procurement request and sets basic parameters."""
    inp = state.get("input") or {}
    tonnage = float(inp.get("tonnage", 0.0))
    port = str(inp.get("delivery_port", "UNKNOWN"))

    return {
        "log": [f"{UNISPSC_CODE}:verify_requisition: Tonnage={tonnage}, Port={port}"],
        "tonnage": tonnage,
        "delivery_port": port,
        "supplier_vetted": True if inp.get("supplier_id") else False
    }


def analyze_quality_specs(state: State) -> dict[str, Any]:
    """Evaluates coal quality requirements such as calorific value and sulfur limits."""
    inp = state.get("input") or {}
    cv = int(inp.get("calorific_value", 5500))
    sulfur = float(inp.get("sulfur_max", 1.0))

    # Simple logic: higher CV coal is logged as high-grade
    grade = "HIGH" if cv > 6000 else "STANDARD"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_quality_specs: Grade={grade}, CV={cv}, Sulfur={sulfur}"],
        "calorific_value_kcal": cv,
        "sulfur_content_pct": sulfur
    }


def authorize_order(state: State) -> dict[str, Any]:
    """Finalizes the procurement result based on vetted status and specs."""
    vetted = state.get("supplier_vetted", False)
    tonnage = state.get("tonnage", 0.0)

    status = "APPROVED" if (vetted and tonnage > 0) else "PENDING_REVIEW"

    return {
        "log": [f"{UNISPSC_CODE}:authorize_order: Status={status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": status,
            "tonnage_final": tonnage,
            "vetted": vetted,
            "ok": True if status == "APPROVED" else False
        },
    }


_g = StateGraph(State)
_g.add_node("verify_requisition", verify_requisition)
_g.add_node("analyze_quality_specs", analyze_quality_specs)
_g.add_node("authorize_order", authorize_order)

_g.add_edge(START, "verify_requisition")
_g.add_edge("verify_requisition", "analyze_quality_specs")
_g.add_edge("analyze_quality_specs", "authorize_order")
_g.add_edge("authorize_order", END)

graph = _g.compile()
