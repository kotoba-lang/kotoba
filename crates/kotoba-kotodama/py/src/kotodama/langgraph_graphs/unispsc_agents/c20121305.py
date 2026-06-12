# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121305"
UNISPSC_TITLE = "Bearing Procurement"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121305"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Bearing Procurement
    bearing_type: str
    load_rating_kn: float
    vendor_match_id: str
    procurement_status: str


def verify_specifications(state: State) -> dict[str, Any]:
    """Validates technical requirements for the requested bearing."""
    inp = state.get("input") or {}
    b_type = inp.get("bearing_type", "standard-ball")
    load = float(inp.get("load_rating", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:verify_specifications"],
        "bearing_type": b_type,
        "load_rating_kn": load,
        "procurement_status": "specifications_verified" if load > 0 else "invalid_specs"
    }


def match_vendor(state: State) -> dict[str, Any]:
    """Identifies a certified vendor for the specified bearing specs."""
    b_type = state.get("bearing_type", "standard")
    # Simulate vendor lookup logic
    v_id = f"V-BRG-{b_type.upper()[:3]}-X1"
    return {
        "log": [f"{UNISPSC_CODE}:match_vendor"],
        "vendor_match_id": v_id,
        "procurement_status": "vendor_sourced"
    }


def authorize_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement result and generates the authorization token."""
    status = state.get("procurement_status")
    v_id = state.get("vendor_match_id", "NONE")
    success = status == "vendor_sourced"

    return {
        "log": [f"{UNISPSC_CODE}:authorize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "vendor_id": v_id,
            "ok": success,
            "status": "authorized" if success else "failed"
        }
    }


_g = StateGraph(State)
_g.add_node("verify", verify_specifications)
_g.add_node("match", match_vendor)
_g.add_node("authorize", authorize_procurement)

_g.add_edge(START, "verify")
_g.add_edge("verify", "match")
_g.add_edge("match", "authorize")
_g.add_edge("authorize", END)

graph = _g.compile()
