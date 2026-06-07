# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11111502 — Commodity.

Bespoke graph logic for handling livestock commodities within segment 11.
This agent validates origin, performs quality inspections, and emits
standardized commodity results.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11111502"
UNISPSC_TITLE = "Commodity"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11111502"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Livestock Commodity
    lot_origin: str
    grade_certification: bool
    inspection_status: str
    quantity_head: int


def intake(state: State) -> dict[str, Any]:
    """Receives the commodity lot and initializes the state."""
    inp = state.get("input") or {}
    origin = inp.get("origin", "unknown")
    quantity = int(inp.get("quantity", 0))

    return {
        "log": [f"{UNISPSC_CODE}:intake - Received lot of {quantity} from {origin}"],
        "lot_origin": origin,
        "quantity_head": quantity,
        "inspection_status": "pending",
    }


def inspect(state: State) -> dict[str, Any]:
    """Performs grade certification and quality inspection."""
    quantity = state.get("quantity_head", 0)
    origin = state.get("lot_origin", "unknown")

    # Simple logic to simulate inspection
    certified = quantity > 0 and origin != "unknown"
    status = "passed" if certified else "failed"

    return {
        "log": [f"{UNISPSC_CODE}:inspect - Inspection {status}"],
        "grade_certification": certified,
        "inspection_status": status,
    }


def finalize(state: State) -> dict[str, Any]:
    """Constructs the final result based on the inspection outcome."""
    status = state.get("inspection_status")
    certified = state.get("grade_certification", False)

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "certified": certified,
        "status": status,
        "ok": status == "passed",
    }

    return {
        "log": [f"{UNISPSC_CODE}:finalize - Emitting result"],
        "result": res,
    }


_g = StateGraph(State)
_g.add_node("intake", intake)
_g.add_node("inspect", inspect)
_g.add_node("finalize", finalize)

_g.add_edge(START, "intake")
_g.add_edge("intake", "inspect")
_g.add_edge("inspect", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
