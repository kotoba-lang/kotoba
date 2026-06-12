# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c15121527 — Steel Procurement (segment 15).

Bespoke logic for steel procurement workflows, including specification
validation, supplier vetting, and order finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "15121527"
UNISPSC_TITLE = "Steel Procurement"
UNISPSC_SEGMENT = "15"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c15121527"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    material_spec_verified: bool
    supplier_vetted: bool
    procurement_batch_id: str


def validate_specs(state: State) -> dict[str, Any]:
    """Verify steel grade and dimensions against procurement requirements."""
    inp = state.get("input") or {}
    # Simulate validation: requires grade, thickness, and positive quantity
    grade = inp.get("grade")
    thickness = inp.get("thickness_mm")
    quantity = inp.get("quantity_tons", 0)
    is_valid = bool(grade and thickness and quantity > 0)

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs:{'ok' if is_valid else 'fail'}"],
        "material_spec_verified": is_valid,
    }


def vet_supplier(state: State) -> dict[str, Any]:
    """Check supplier credentials and availability for the requested steel."""
    inp = state.get("input") or {}
    supplier = str(inp.get("supplier_id", "unknown"))
    # Simulate vetting logic: IDs starting with 'CERT-' are pre-vetted
    is_vetted = supplier.startswith("CERT-") or supplier == "trusted_foundry_01"

    return {
        "log": [f"{UNISPSC_CODE}:vet_supplier:{'vetted' if is_vetted else 'provisional'}"],
        "supplier_vetted": is_vetted,
        "procurement_batch_id": f"STEEL-ORD-{abs(hash(supplier)) % 10000:04d}",
    }


def finalize_order(state: State) -> dict[str, Any]:
    """Compile final procurement result based on validation and vetting."""
    is_valid = state.get("material_spec_verified", False)
    is_vetted = state.get("supplier_vetted", False)
    batch_id = state.get("procurement_batch_id", "N/A")

    success = is_valid and is_vetted

    return {
        "log": [f"{UNISPSC_CODE}:finalize_order:{'approved' if success else 'rejected'}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "batch_id": batch_id,
            "status": "APPROVED" if success else "REJECTED_INCOMPLETE_DATA",
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specs", validate_specs)
_g.add_node("vet_supplier", vet_supplier)
_g.add_node("finalize_order", finalize_order)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "vet_supplier")
_g.add_edge("vet_supplier", "finalize_order")
_g.add_edge("finalize_order", END)

graph = _g.compile()
