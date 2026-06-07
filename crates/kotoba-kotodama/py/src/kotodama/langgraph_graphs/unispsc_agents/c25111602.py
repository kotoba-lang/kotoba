# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Bespoke LangGraph agent for UNISPSC 25111602 — Vessel.
Segment 25: Commercial and Military and Private Vehicles and their Accessories and Components.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111602"
UNISPSC_TITLE = "Vessel"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111602"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for maritime vessel management
    vessel_id: str
    imo_number: str
    displacement_tons: float
    registry_verified: bool
    structural_integrity_check: str


def inspect_vessel_registry(state: State) -> dict[str, Any]:
    """Verify the official maritime registry records and IMO designation."""
    inp = state.get("input") or {}
    imo = inp.get("imo", "IMO-UNKNOWN")
    v_name = inp.get("vessel_name", "UNNAMED-VESSEL")

    # Simple validation logic for bespoke actor simulation
    is_valid = imo.startswith("IMO-") and len(imo) > 7

    return {
        "log": [f"{UNISPSC_CODE}:inspect_vessel_registry"],
        "imo_number": imo,
        "vessel_id": v_name,
        "registry_verified": is_valid
    }


def analyze_ballast_and_load(state: State) -> dict[str, Any]:
    """Calculate total displacement based on hull deadweight and current cargo load."""
    inp = state.get("input") or {}
    deadweight = float(inp.get("deadweight", 1000.0))
    cargo_load = float(inp.get("cargo_load", 0.0))

    total_displacement = deadweight + cargo_load
    integrity = "PASS" if cargo_load < (deadweight * 1.5) else "CRITICAL_LOAD_WARNING"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_ballast_and_load"],
        "displacement_tons": total_displacement,
        "structural_integrity_check": integrity
    }


def finalize_operational_status(state: State) -> dict[str, Any]:
    """Synthesize registry and mechanical data into a final vessel certification."""
    is_verified = state.get("registry_verified", False)
    integrity = state.get("structural_integrity_check", "UNKNOWN")
    displacement = state.get("displacement_tons", 0.0)

    ready = is_verified and integrity == "PASS"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_operational_status"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "vessel_manifest": {
                "name": state.get("vessel_id"),
                "imo": state.get("imo_number"),
                "displacement": displacement,
                "integrity": integrity
            },
            "operational_clearance": ready,
            "status": "APPROVED" if ready else "HELD_FOR_INSPECTION"
        }
    }


_g = StateGraph(State)

_g.add_node("inspect_vessel_registry", inspect_vessel_registry)
_g.add_node("analyze_ballast_and_load", analyze_ballast_and_load)
_g.add_node("finalize_operational_status", finalize_operational_status)

_g.add_edge(START, "inspect_vessel_registry")
_g.add_edge("inspect_vessel_registry", "analyze_ballast_and_load")
_g.add_edge("analyze_ballast_and_load", "finalize_operational_status")
_g.add_edge("finalize_operational_status", END)

graph = _g.compile()
