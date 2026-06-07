# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11101604 — Metal Procurement (segment 11).

Bespoke logic for orchestrating metal resource acquisition, ensuring
specification compliance, and metallurgical quality verification within
the mineral and mining procurement lifecycle.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11101604"
UNISPSC_TITLE = "Metal Procurement"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11101604"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Metal Procurement
    metal_specification: str
    required_purity: float
    tonnage: float
    compliance_verified: bool
    procurement_status: str


def validate_procurement_specs(state: State) -> dict[str, Any]:
    """Validates the input specifications for the metal procurement request."""
    inp = state.get("input") or {}
    spec = inp.get("specification", "Standard Industrial Grade")
    purity = float(inp.get("min_purity", 0.90))
    qty = float(inp.get("quantity_tons", 1.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_procurement_specs"],
        "metal_specification": spec,
        "required_purity": purity,
        "tonnage": qty,
    }


def verify_metallurgical_compliance(state: State) -> dict[str, Any]:
    """Simulates a verification check against industry metallurgical standards."""
    purity = state.get("required_purity", 0.0)
    spec = state.get("metal_specification", "")

    # Logic: High purity requests for standard grade require extra verification
    verified = True
    if purity > 0.99 and "Standard" in spec:
        verified = False

    return {
        "log": [f"{UNISPSC_CODE}:verify_metallurgical_compliance"],
        "compliance_verified": verified,
    }


def authorize_and_emit(state: State) -> dict[str, Any]:
    """Finalizes the procurement transaction if compliance is met."""
    verified = state.get("compliance_verified", False)
    qty = state.get("tonnage", 0.0)

    status = "AUTHORIZED" if (verified and qty > 0) else "REJECTED_SPEC_MISMATCH"

    return {
        "log": [f"{UNISPSC_CODE}:authorize_and_emit"],
        "procurement_status": status,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "status": status,
            "metadata": {
                "spec": state.get("metal_specification"),
                "purity": state.get("required_purity"),
                "tons": qty,
            },
            "ok": verified,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_specs", validate_procurement_specs)
_g.add_node("verify_compliance", verify_metallurgical_compliance)
_g.add_node("authorize", authorize_and_emit)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "verify_compliance")
_g.add_edge("verify_compliance", "authorize")
_g.add_edge("authorize", END)

graph = _g.compile()
