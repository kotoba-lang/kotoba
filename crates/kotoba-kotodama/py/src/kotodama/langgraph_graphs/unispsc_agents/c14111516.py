# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14111516"
UNISPSC_TITLE = "Paper Supply"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14111516"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    paper_format: str
    sheet_count: int
    warehouse_id: str
    allocation_confirmed: bool


def validate_procurement(state: State) -> dict[str, Any]:
    """Validates the paper supply request parameters."""
    inp = state.get("input") or {}
    paper_format = inp.get("format", "A4")
    count = inp.get("count", 0)

    log_entry = f"{UNISPSC_CODE}:validate_procurement: {paper_format} (qty: {count})"
    return {
        "log": [log_entry],
        "paper_format": paper_format,
        "sheet_count": count,
        "warehouse_id": "WH-REGION-01"
    }


def inventory_check(state: State) -> dict[str, Any]:
    """Checks stock levels for the requested paper format in the local warehouse."""
    count = state.get("sheet_count", 0)
    # Business logic: max single order fulfillment limit is 5000 sheets
    available = 0 < count <= 5000

    log_entry = f"{UNISPSC_CODE}:inventory_check: {'available' if available else 'insufficient'}"
    return {
        "log": [log_entry],
        "allocation_confirmed": available
    }


def dispatch_supply(state: State) -> dict[str, Any]:
    """Finalizes the allocation and prepares the dispatch record."""
    confirmed = state.get("allocation_confirmed", False)

    log_entry = f"{UNISPSC_CODE}:dispatch_supply: {'completed' if confirmed else 'failed'}"
    return {
        "log": [log_entry],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "dispatched" if confirmed else "rejected_stock_level",
            "format": state.get("paper_format"),
            "count": state.get("sheet_count"),
            "ok": confirmed,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_procurement)
_g.add_node("inventory", inventory_check)
_g.add_node("dispatch", dispatch_supply)

_g.add_edge(START, "validate")
_g.add_edge("validate", "inventory")
_g.add_edge("inventory", "dispatch")
_g.add_edge("dispatch", END)

graph = _g.compile()
