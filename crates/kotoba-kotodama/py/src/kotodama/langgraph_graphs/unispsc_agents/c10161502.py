# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10161502"
UNISPSC_TITLE = "Livestock"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10161502"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    species: str
    herd_id: str
    health_status: str
    quarantine_verified: bool
    inspection_passed: bool


def validate_consignment(state: State) -> dict[str, Any]:
    """Validates the incoming livestock consignment data."""
    inp = state.get("input") or {}
    species = inp.get("species", "Bovine")
    herd_id = inp.get("herd_id", "LIVESTOCK-REQ-001")
    return {
        "log": [f"{UNISPSC_CODE}:validate_consignment id={herd_id}"],
        "species": species,
        "herd_id": herd_id,
        "health_status": "pending",
    }


def perform_health_inspection(state: State) -> dict[str, Any]:
    """Simulates a domain health inspection for the livestock lot."""
    # Logical transition for livestock safety protocols
    return {
        "log": [f"{UNISPSC_CODE}:perform_health_inspection verified=true"],
        "health_status": "cleared",
        "quarantine_verified": True,
        "inspection_passed": True,
    }


def finalize_livestock_record(state: State) -> dict[str, Any]:
    """Finalizes the asset record and emits the completion result."""
    passed = state.get("inspection_passed", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_livestock_record status={'OK' if passed else 'FAIL'}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "herd_id": state.get("herd_id"),
            "species": state.get("species"),
            "health_clearance": passed,
            "ok": passed,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_consignment)
_g.add_node("inspect", perform_health_inspection)
_g.add_node("finalize", finalize_livestock_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "inspect")
_g.add_edge("inspect", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
