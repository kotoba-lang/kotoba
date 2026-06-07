# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12352310"
UNISPSC_TITLE = "Commodity"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12352310"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    purity_level: float
    sds_verified: bool
    batch_tracking_id: str
    hazmat_certified: bool


def inspect_purity(state: State) -> dict[str, Any]:
    """Inspects the chemical purity of the commodity for Segment 12 compliance."""
    inp = state.get("input") or {}
    purity = float(inp.get("purity", 0.99))
    return {
        "log": [f"{UNISPSC_CODE}:inspect_purity"],
        "purity_level": purity,
    }


def verify_compliance(state: State) -> dict[str, Any]:
    """Verifies safety data sheets and hazardous material certification."""
    inp = state.get("input") or {}
    has_sds = inp.get("sds", True)
    hazmat = inp.get("hazmat_audit", True)
    return {
        "log": [f"{UNISPSC_CODE}:verify_compliance"],
        "sds_verified": has_sds,
        "hazmat_certified": hazmat,
    }


def finalize_commodity_record(state: State) -> dict[str, Any]:
    """Finalizes the tracking record and emits the certification result."""
    purity = state.get("purity_level", 0.0)
    compliant = state.get("sds_verified", False) and state.get("hazmat_certified", False)
    tracking_id = f"REF-{UNISPSC_CODE}-{id(state) % 1000}"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_commodity_record"],
        "batch_tracking_id": tracking_id,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "purity": purity,
            "tracking_id": tracking_id,
            "verified": compliant,
            "status": "APPROVED" if (purity > 0.95 and compliant) else "REVIEW_REQUIRED",
            "ok": compliant,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_purity)
_g.add_node("verify", verify_compliance)
_g.add_node("finalize", finalize_commodity_record)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
