# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25202606 — Aircraft Spec (segment 25).

This bespoke implementation handles the ingestion, validation, and
cataloging of technical aircraft specifications, including airframe
parameters and powerplant configurations.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25202606"
UNISPSC_TITLE = "Aircraft Spec"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25202606"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Aircraft Spec
    airframe_id: str
    mtow_kg: float
    engine_config: str
    certification_basis: str
    is_validated: bool


def ingest_airframe_data(state: State) -> dict[str, Any]:
    """Extracts basic airframe identification and weight data."""
    inp = state.get("input") or {}
    model = str(inp.get("model", "Unknown-Platform"))
    weight = float(inp.get("mtow", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:ingest_airframe_data:{model}"],
        "airframe_id": model,
        "mtow_kg": weight,
    }


def validate_powerplant_spec(state: State) -> dict[str, Any]:
    """Verifies the engine configuration and assigns certification basis."""
    inp = state.get("input") or {}
    config = str(inp.get("engines", "Twin-Turbofan"))

    # Simple validation logic based on MTOW
    mtow = state.get("mtow_kg", 0.0)
    basis = "CS-25" if mtow > 5700 else "CS-23"

    return {
        "log": [f"{UNISPSC_CODE}:validate_powerplant_spec:{config}"],
        "engine_config": config,
        "certification_basis": basis,
        "is_validated": mtow > 0,
    }


def compile_aircraft_record(state: State) -> dict[str, Any]:
    """Finalizes the aircraft specification record for the registry."""
    is_valid = state.get("is_validated", False)

    return {
        "log": [f"{UNISPSC_CODE}:compile_aircraft_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "spec_sheet": {
                "airframe": state.get("airframe_id"),
                "mtow_kg": state.get("mtow_kg"),
                "propulsion": state.get("engine_config"),
                "regulatory_basis": state.get("certification_basis"),
            },
            "status": "verified" if is_valid else "draft",
        },
    }


_g = StateGraph(State)

_g.add_node("ingest", ingest_airframe_data)
_g.add_node("validate", validate_powerplant_spec)
_g.add_node("compile", compile_aircraft_record)

_g.add_edge(START, "ingest")
_g.add_edge("ingest", "validate")
_g.add_edge("validate", "compile")
_g.add_edge("compile", END)

graph = _g.compile()
