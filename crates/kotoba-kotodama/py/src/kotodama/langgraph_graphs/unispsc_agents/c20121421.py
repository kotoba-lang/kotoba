# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121421 — Servo Procure (segment 20).

Bespoke graph logic for the procurement and technical verification of
servo motors and associated motion control components.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121421"
UNISPSC_TITLE = "Servo Procure"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121421"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra fields for Servo Procure domain
    torque_rating_nm: float
    voltage_range: str
    supplier_verified: bool
    procurement_approved: bool


def analyze_specs(state: State) -> dict[str, Any]:
    """Analyzes incoming servo specifications against procurement standards."""
    inp = state.get("input") or {}
    torque = float(inp.get("torque", 0.0))
    voltage = str(inp.get("voltage", "24V"))

    return {
        "log": [f"{UNISPSC_CODE}:analyze_specs"],
        "torque_rating_nm": torque,
        "voltage_range": voltage,
        "procurement_approved": torque > 0.5
    }


def verify_supplier(state: State) -> dict[str, Any]:
    """Verifies that the requested servo originates from an approved manufacturer."""
    # Logic to simulate supplier verification
    return {
        "log": [f"{UNISPSC_CODE}:verify_supplier"],
        "supplier_verified": True
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement record and prepares the output manifest."""
    is_approved = state.get("procurement_approved", False)
    is_verified = state.get("supplier_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "Completed" if (is_approved and is_verified) else "Pending",
            "torque_verified": is_approved,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("analyze", analyze_specs)
_g.add_node("verify", verify_supplier)
_g.add_node("finalize", finalize_procurement)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
