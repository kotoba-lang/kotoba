# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23201001 — Vehicle (segment 23).

Bespoke graph logic for vehicle asset management and compliance verification.
This agent processes vehicle identification, evaluates safety/emission
standards, and issues a registry-ready result object.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23201001"
UNISPSC_TITLE = "Vehicle"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23201001"


class State(TypedDict, total=False):
    # Required fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific fields for Vehicle
    vin: str
    make_model: str
    emission_tier: int
    inspection_passed: bool
    registry_status: str


def intake_vehicle(state: State) -> dict[str, Any]:
    """Extracts vehicle metadata from the input payload."""
    inp = state.get("input") or {}
    vin = str(inp.get("vin", "UNDEFINED")).upper()
    make = inp.get("make", "Unknown")
    model = inp.get("model", "Generic")

    return {
        "log": [f"{UNISPSC_CODE}:intake_vehicle - VIN:{vin}"],
        "vin": vin,
        "make_model": f"{make} {model}",
        "registry_status": "PENDING",
    }


def evaluate_compliance(state: State) -> dict[str, Any]:
    """Simulates checking the vehicle against safety and emission standards."""
    vin = state.get("vin", "")
    # Simulation: VINs starting with 'V' or having 17 chars pass
    is_valid_vin = len(vin) == 17 or vin.startswith("V")
    tier = 4 if is_valid_vin else 0

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_compliance - Tier {tier}"],
        "inspection_passed": is_valid_vin,
        "emission_tier": tier,
    }


def finalize_record(state: State) -> dict[str, Any]:
    """Generates the final registry certificate and result object."""
    passed = state.get("inspection_passed", False)
    status = "REGISTERED" if passed else "REJECTED"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_record - {status}"],
        "registry_status": status,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "vin": state.get("vin"),
            "make_model": state.get("make_model"),
            "emission_tier": state.get("emission_tier"),
            "ok": passed,
            "status": status,
        },
    }


_g = StateGraph(State)

_g.add_node("intake_vehicle", intake_vehicle)
_g.add_node("evaluate_compliance", evaluate_compliance)
_g.add_node("finalize_record", finalize_record)

_g.add_edge(START, "intake_vehicle")
_g.add_edge("intake_vehicle", "evaluate_compliance")
_g.add_edge("evaluate_compliance", "finalize_record")
_g.add_edge("finalize_record", END)

graph = _g.compile()
