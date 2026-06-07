# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122902 — Seal (segment 20).

Bespoke graph logic for industrial/mining seals used in well drilling and completion.
This agent validates material specifications, simulates pressure testing, and
certifies the seal for deployment in drilling operations.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122902"
UNISPSC_TITLE = "Seal"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122902"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Seal (Well Drilling context)
    material_composition: str
    pressure_rating_psi: int
    leak_test_status: str
    certification_id: str
    integrity_verified: bool


def validate_spec(state: State) -> dict[str, Any]:
    """Validates the seal material and mechanical specifications."""
    inp = state.get("input") or {}
    material = inp.get("material", "Elastomeric Polymer")
    pressure = inp.get("max_pressure_psi", 10000)

    return {
        "log": [f"{UNISPSC_CODE}:validate_spec -> material={material}"],
        "material_composition": material,
        "pressure_rating_psi": pressure,
        "integrity_verified": pressure > 0,
    }


def perform_leak_test(state: State) -> dict[str, Any]:
    """Simulates a non-destructive pressure and leak test on the seal."""
    verified = state.get("integrity_verified", False)
    status = "Passed" if verified else "Failed"

    return {
        "log": [f"{UNISPSC_CODE}:perform_leak_test -> status={status}"],
        "leak_test_status": status,
    }


def certify_seal(state: State) -> dict[str, Any]:
    """Finalizes the certification and prepares the deployment record."""
    test_passed = state.get("leak_test_status") == "Passed"
    cert_id = f"CERT-{UNISPSC_CODE}-2026-X" if test_passed else "REJECTED"

    return {
        "log": [f"{UNISPSC_CODE}:certify_seal -> cert_id={cert_id}"],
        "certification_id": cert_id,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certified": test_passed,
            "certification_id": cert_id,
            "ok": test_passed,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_spec)
_g.add_node("inspect", perform_leak_test)
_g.add_node("certify", certify_seal)

_g.add_edge(START, "validate")
_g.add_edge("validate", "inspect")
_g.add_edge("inspect", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
