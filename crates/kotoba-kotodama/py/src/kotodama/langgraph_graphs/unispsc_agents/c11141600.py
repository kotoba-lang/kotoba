# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11141600 — Chemical Procurement (segment 11).

Bespoke graph logic for chemical procurement workflows, including
regulatory compliance verification, safety data sheet (SDS) validation,
and procurement order generation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11141600"
UNISPSC_TITLE = "Chemical Procurement"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11141600"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke fields for Chemical Procurement
    sds_verified: bool
    hazard_class: str
    regulatory_clearance: bool
    procurement_id: str


def validate_regulatory_compliance(state: State) -> dict[str, Any]:
    """Ensures chemicals meet safety and regulatory standards."""
    inp = state.get("input") or {}
    chemical_name = str(inp.get("chemical_name", "generic_chemical"))
    # Simulate a regulatory check: certain substances might be flagged
    cleared = chemical_name.lower() != "restricted_substance"
    return {
        "log": [f"{UNISPSC_CODE}:validate_regulatory_compliance"],
        "regulatory_clearance": cleared,
        "hazard_class": inp.get("hazard_class", "Standard-Grade"),
    }


def verify_safety_data(state: State) -> dict[str, Any]:
    """Verifies that Safety Data Sheets (SDS) are present and valid."""
    cleared = state.get("regulatory_clearance", False)
    # SDS verification is mocked to follow the regulatory clearance status
    return {
        "log": [f"{UNISPSC_CODE}:verify_safety_data"],
        "sds_verified": cleared,
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Generates the final procurement record and approval status."""
    sds_ok = state.get("sds_verified", False)
    reg_ok = state.get("regulatory_clearance", False)
    p_id = f"CHEM-ORD-{UNISPSC_CODE}-AX"

    success = sds_ok and reg_ok

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "procurement_id": p_id,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "procurement_id": p_id,
            "hazard_class": state.get("hazard_class"),
            "status": "APPROVED" if success else "REJECTED_COMPLIANCE_FAILURE",
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_regulatory_compliance)
_g.add_node("verify_sds", verify_safety_data)
_g.add_node("finalize", finalize_procurement)

_g.add_edge(START, "validate")
_g.add_edge("validate", "verify_sds")
_g.add_edge("verify_sds", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
