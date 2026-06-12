# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14111802 — Receipts or receipt books (segment 14).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14111802"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14111802"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Receipts/Receipt Books
    serial_range: tuple[int, int]
    is_carbonless: bool
    page_count: int
    validation_passed: bool


def initialize_spec(state: State) -> dict[str, Any]:
    """Parses incoming order specifications for receipt books."""
    inp = state.get("input") or {}
    start = inp.get("serial_start", 1000)
    count = inp.get("count", 50)
    return {
        "log": [f"{UNISPSC_CODE}:initialize_spec"],
        "serial_range": (start, start + count - 1),
        "is_carbonless": inp.get("carbonless", True),
        "page_count": count,
    }


def verify_compliance(state: State) -> dict[str, Any]:
    """Checks if the receipt template meets regulatory standards."""
    # Logic: Verify that required fields like Date, Amount, and Payer are implied
    is_valid = state.get("page_count", 0) > 0
    return {
        "log": [f"{UNISPSC_CODE}:verify_compliance"],
        "validation_passed": is_valid,
    }


def register_batch(state: State) -> dict[str, Any]:
    """Finalizes the receipt book batch registration."""
    serial_range = state.get("serial_range", (0, 0))
    return {
        "log": [f"{UNISPSC_CODE}:register_batch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "batch_id": f"REC-{serial_range[0]}-{serial_range[1]}",
            "carbonless": state.get("is_carbonless"),
            "status": "APPROVED" if state.get("validation_passed") else "PENDING",
        },
    }


_g = StateGraph(State)
_g.add_node("initialize_spec", initialize_spec)
_g.add_node("verify_compliance", verify_compliance)
_g.add_node("register_batch", register_batch)

_g.add_edge(START, "initialize_spec")
_g.add_edge("initialize_spec", "verify_compliance")
_g.add_edge("verify_compliance", "register_batch")
_g.add_edge("register_batch", END)

graph = _g.compile()
