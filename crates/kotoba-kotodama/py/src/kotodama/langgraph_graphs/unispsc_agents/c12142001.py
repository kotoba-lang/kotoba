# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12142001"
UNISPSC_TITLE = "Aln Procurement"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12142001"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Animal (Aln) Procurement
    vendor_authorized: bool
    quarantine_status: str
    health_cert_id: str
    transport_method: str


def validate_vendor(state: State) -> dict[str, Any]:
    """Checks if the vendor is qualified for handling live animal materials."""
    inp = state.get("input") or {}
    vendor_id = inp.get("vendor_id", "DEFAULT_VENDOR")
    is_authorized = str(vendor_id).startswith("AUTH-")

    return {
        "log": [f"{UNISPSC_CODE}:validate_vendor:{vendor_id}"],
        "vendor_authorized": is_authorized,
        "transport_method": inp.get("transport", "ground"),
    }


def evaluate_quarantine_needs(state: State) -> dict[str, Any]:
    """Determines if the animal lot requires quarantine based on origin and health status."""
    if not state.get("vendor_authorized"):
        return {
            "log": [f"{UNISPSC_CODE}:evaluate_quarantine:aborted_unauthorized"],
            "quarantine_status": "REJECTED",
        }

    inp = state.get("input") or {}
    origin = inp.get("origin", "domestic")
    needs_q = "REQUIRED" if origin != "domestic" else "WAIVED"

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_quarantine:{origin}"],
        "quarantine_status": needs_q,
        "health_cert_id": f"CERT-{UNISPSC_CODE}-{origin.upper()[:3]}",
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement order for the live animal material."""
    q_status = state.get("quarantine_status", "UNKNOWN")
    success = state.get("vendor_authorized", False) and q_status != "REJECTED"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement:{q_status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "order_id": f"PO-1214-{UNISPSC_CODE}-AX",
            "quarantine": q_status,
            "health_certificate": state.get("health_cert_id"),
            "transport": state.get("transport_method"),
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_vendor", validate_vendor)
_g.add_node("evaluate_quarantine", evaluate_quarantine_needs)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "validate_vendor")
_g.add_edge("validate_vendor", "evaluate_quarantine")
_g.add_edge("evaluate_quarantine", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
