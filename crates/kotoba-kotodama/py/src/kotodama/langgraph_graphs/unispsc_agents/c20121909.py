# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121909 — Gear Procurement (segment 20).

Bespoke graph for gear procurement logistics, handling specification verification,
supplier vetting, and order finalization.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121909"
UNISPSC_TITLE = "Gear Procurement"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121909"


class State(TypedDict, total=False):
    # Core fields
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]

    # Domain: Gear Procurement
    gear_type: str
    gear_specs_verified: bool
    supplier_authorized: bool
    procurement_id: str
    risk_assessment_score: float


def verify_gear_specs(state: State) -> dict[str, Any]:
    """Checks that the gear requested meets technical standards."""
    inp = state.get("input") or {}
    specs = inp.get("specifications", {})
    g_type = inp.get("gear_type", "unspecified")

    # Verification simulation
    verified = bool(specs) and g_type != "unspecified"

    return {
        "log": [f"{UNISPSC_CODE}:verify_gear_specs"],
        "gear_type": g_type,
        "gear_specs_verified": verified,
    }


def authorize_supplier(state: State) -> dict[str, Any]:
    """Validates the vendor for the specific gear segment."""
    inp = state.get("input") or {}
    vendor_id = inp.get("vendor_id", "anonymous")

    # Authorization logic: vendor must have valid format and specs must be verified
    authorized = state.get("gear_specs_verified", False) and vendor_id.startswith("VEN-")

    return {
        "log": [f"{UNISPSC_CODE}:authorize_supplier"],
        "supplier_authorized": authorized,
        "risk_assessment_score": 0.15 if authorized else 0.85,
    }


def finalize_order(state: State) -> dict[str, Any]:
    """Finalizes the procurement transaction records."""
    is_ok = state.get("supplier_authorized", False)
    p_id = f"PROC-{UNISPSC_CODE}-77" if is_ok else "NA"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_order"],
        "procurement_id": p_id,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "order_id": p_id,
            "status": "APPROVED" if is_ok else "REJECTED",
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("verify_gear_specs", verify_gear_specs)
_g.add_node("authorize_supplier", authorize_supplier)
_g.add_node("finalize_order", finalize_order)

_g.add_edge(START, "verify_gear_specs")
_g.add_edge("verify_gear_specs", "authorize_supplier")
_g.add_edge("authorize_supplier", "finalize_order")
_g.add_edge("finalize_order", END)

graph = _g.compile()
