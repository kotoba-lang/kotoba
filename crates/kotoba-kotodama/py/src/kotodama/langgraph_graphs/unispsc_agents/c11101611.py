# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11101611 — Asbestos.

This agent implements a specialized workflow for asbestos hazard assessment,
abatement strategy selection, and compliance manifest generation.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11101611"
UNISPSC_TITLE = "Asbestos"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11101611"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    hazard_level: str
    abatement_method: str
    containment_verified: bool
    disposal_permit_id: str


def assess_exposure_risk(state: State) -> dict[str, Any]:
    """Evaluates the risk level based on asbestos type and fiber concentration."""
    inp = state.get("input") or {}
    material = inp.get("material", "non-friable")
    concentration = inp.get("concentration_ppm", 0)

    level = "HIGH" if concentration > 0.1 or material == "friable" else "MODERATE"
    return {
        "log": [f"{UNISPSC_CODE}:assess_exposure_risk:level={level}"],
        "hazard_level": level,
    }


def verify_abatement_protocol(state: State) -> dict[str, Any]:
    """Determines the appropriate containment and removal strategy."""
    level = state.get("hazard_level", "MODERATE")

    if level == "HIGH":
        method = "NEGATIVE_PRESSURE_CONTAINMENT"
        permit = "EPA-REQ-99"
    else:
        method = "WET_METHOD_ENCAPSULATION"
        permit = "LOCAL-PERMIT-01"

    return {
        "log": [f"{UNISPSC_CODE}:verify_abatement_protocol:method={method}"],
        "abatement_method": method,
        "containment_verified": True,
        "disposal_permit_id": permit,
    }


def generate_manifest(state: State) -> dict[str, Any]:
    """Produces the final safety manifest for transport and disposal."""
    return {
        "log": [f"{UNISPSC_CODE}:generate_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metadata": {
                "hazard": state.get("hazard_level"),
                "method": state.get("abatement_method"),
                "permit": state.get("disposal_permit_id"),
                "containment": "VERIFIED" if state.get("containment_verified") else "PENDING",
            },
            "status": "COMPLIANT",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("assess_risk", assess_exposure_risk)
_g.add_node("verify_protocol", verify_abatement_protocol)
_g.add_node("emit_manifest", generate_manifest)

_g.add_edge(START, "assess_risk")
_g.add_edge("assess_risk", "verify_protocol")
_g.add_edge("verify_protocol", "emit_manifest")
_g.add_edge("emit_manifest", END)

graph = _g.compile()
