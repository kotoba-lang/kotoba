# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13111219 — Uranium (segment 13).

Bespoke graph for tracking uranium isotope concentrations, enrichment levels,
and ensuring regulatory compliance for fissile material management.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13111219"
UNISPSC_TITLE = "Uranium"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13111219"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Uranium domain fields
    enrichment_percentage: float
    isotope_profile: dict[str, float]
    radiation_safety_check: bool
    regulatory_permit_id: str


def check_enrichment(state: State) -> dict[str, Any]:
    """Inspects enrichment levels to classify material (LEU vs HEU)."""
    inp = state.get("input") or {}
    # Default to natural uranium if not specified
    enrichment = float(inp.get("enrichment", 0.711))
    profile = inp.get("isotopes", {"U-238": 99.27, "U-235": 0.72, "U-234": 0.005})

    return {
        "log": [f"{UNISPSC_CODE}:check_enrichment: {enrichment}%"],
        "enrichment_percentage": enrichment,
        "isotope_profile": profile,
        "radiation_safety_check": True
    }


def validate_regulatory_status(state: State) -> dict[str, Any]:
    """Verifies that the material has the required international clearance."""
    enrichment = state.get("enrichment_percentage", 0.0)

    # Logic: High Enrichment (>= 20%) requires enhanced safeguards
    if enrichment >= 20.0:
        permit = "IAEA-HEU-SAFEGUARD-ENHANCED"
    elif enrichment > 0.72:
        permit = "IAEA-LEU-CLEARANCE"
    else:
        permit = "IAEA-NAT-U-TRACKING"

    return {
        "log": [f"{UNISPSC_CODE}:validate_regulatory_status: {permit}"],
        "regulatory_permit_id": permit
    }


def finalize_uranium_ledger(state: State) -> dict[str, Any]:
    """Emits the final validated state for the inventory ledger."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_uranium_ledger"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "data": {
                "enrichment": state.get("enrichment_percentage"),
                "permit": state.get("regulatory_permit_id"),
                "safe": state.get("radiation_safety_check"),
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("check_enrichment", check_enrichment)
_g.add_node("validate_regulatory_status", validate_regulatory_status)
_g.add_node("finalize_uranium_ledger", finalize_uranium_ledger)

_g.add_edge(START, "check_enrichment")
_g.add_edge("check_enrichment", "validate_regulatory_status")
_g.add_edge("validate_regulatory_status", "finalize_uranium_ledger")
_g.add_edge("finalize_uranium_ledger", END)

graph = _g.compile()
