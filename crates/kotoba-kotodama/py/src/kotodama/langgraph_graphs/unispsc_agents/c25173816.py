# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25173816 — Clutch Procure (segment 25).

Bespoke graph for the procurement of clutch systems and automotive components.
This agent handles specification validation, inventory verification, and
procurement execution for heavy-duty clutch assemblies.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25173816"
UNISPSC_TITLE = "Clutch Procure"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25173816"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Clutch Procure
    torque_rating_nm: int
    clutch_material: str
    supplier_code: str
    specs_verified: bool
    stock_available: bool


def verify_clutch_specs(state: State) -> dict[str, Any]:
    """Validates the mechanical requirements for the clutch procurement."""
    inp = state.get("input") or {}
    torque = inp.get("torque_rating", 450)
    material = inp.get("material", "ceramic")

    # Logic: ensure torque is within safe operating range
    is_valid = 100 <= torque <= 2500

    return {
        "log": [f"{UNISPSC_CODE}:verify_clutch_specs"],
        "torque_rating_nm": torque,
        "clutch_material": material,
        "specs_verified": is_valid,
    }


def check_supplier_inventory(state: State) -> dict[str, Any]:
    """Checks the supplier database for parts matching the verified specs."""
    material = state.get("clutch_material", "organic")
    verified = state.get("specs_verified", False)

    # Logic: simulate stock availability based on material
    has_stock = verified and (material != "unobtanium")

    return {
        "log": [f"{UNISPSC_CODE}:check_supplier_inventory"],
        "stock_available": has_stock,
        "supplier_code": "VEND-CL-001" if has_stock else "OUT-OF-STOCK",
    }


def finalize_procurement_order(state: State) -> dict[str, Any]:
    """Generates the final procurement order if all checks passed."""
    verified = state.get("specs_verified", False)
    available = state.get("stock_available", False)
    success = verified and available

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement_order"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "APPROVED" if success else "REJECTED",
            "order_id": f"PO-25-{UNISPSC_CODE}-77" if success else None,
            "payload": {
                "torque": state.get("torque_rating_nm"),
                "material": state.get("clutch_material"),
                "supplier": state.get("supplier_code"),
            }
        },
    }


_g = StateGraph(State)

_g.add_node("verify_clutch_specs", verify_clutch_specs)
_g.add_node("check_supplier_inventory", check_supplier_inventory)
_g.add_node("finalize_procurement_order", finalize_procurement_order)

_g.add_edge(START, "verify_clutch_specs")
_g.add_edge("verify_clutch_specs", "check_supplier_inventory")
_g.add_edge("check_supplier_inventory", "finalize_procurement_order")
_g.add_edge("finalize_procurement_order", END)

graph = _g.compile()
