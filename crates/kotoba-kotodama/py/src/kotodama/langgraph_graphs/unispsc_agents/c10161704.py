# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10161704"
UNISPSC_TITLE = "Feed"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10161704"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    feed_category: str
    moisture_level: float
    lot_number: str
    passed_safety: bool


def receive_and_catalog(state: State) -> dict[str, Any]:
    """Logs the arrival of a feed lot and identifies its category."""
    inp = state.get("input") or {}
    category = str(inp.get("category", "Livestock"))
    lot = str(inp.get("lot", "L-DEFAULT"))
    return {
        "log": [f"{UNISPSC_CODE}:receive_and_catalog {lot}"],
        "feed_category": category,
        "lot_number": lot,
    }


def assess_quality(state: State) -> dict[str, Any]:
    """Performs moisture analysis to ensure product stability."""
    inp = state.get("input") or {}
    moisture = float(inp.get("moisture", 12.5))
    # Standard: moisture should be below 15% to prevent mold growth during storage
    is_safe = moisture < 15.0
    return {
        "log": [f"{UNISPSC_CODE}:assess_quality - moisture {moisture}%"],
        "moisture_level": moisture,
        "passed_safety": is_safe,
    }


def finalize_shipment(state: State) -> dict[str, Any]:
    """Compiles results and issues final clearance or rejection."""
    is_safe = state.get("passed_safety", False)
    lot = state.get("lot_number")
    return {
        "log": [f"{UNISPSC_CODE}:finalize_shipment"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "lot_number": lot,
            "status": "APPROVED" if is_safe else "REJECTED",
            "ok": is_safe,
        },
    }


_g = StateGraph(State)

_g.add_node("receive", receive_and_catalog)
_g.add_node("assess", assess_quality)
_g.add_node("finalize", finalize_shipment)

_g.add_edge(START, "receive")
_g.add_edge("receive", "assess")
_g.add_edge("assess", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
