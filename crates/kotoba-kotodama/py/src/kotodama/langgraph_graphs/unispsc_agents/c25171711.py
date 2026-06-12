# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25171711 — Slave Cylinder (segment 25).
Bespoke logic for hydraulic slave cylinder specification validation and pressure testing.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25171711"
UNISPSC_TITLE = "Slave Cylinder"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25171711"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Slave Cylinder
    bore_diameter_mm: float
    fluid_compatibility: str
    test_pressure_psi: int
    seal_integrity_verified: bool


def inspect_specs(state: State) -> dict[str, Any]:
    """Validates the physical and chemical specifications of the slave cylinder."""
    inp = state.get("input") or {}
    bore = inp.get("bore_diameter", 19.05)
    fluid = inp.get("fluid", "DOT3/DOT4")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specs(bore={bore}mm, fluid={fluid})"],
        "bore_diameter_mm": bore,
        "fluid_compatibility": fluid,
    }


def perform_pressure_test(state: State) -> dict[str, Any]:
    """Simulates a static hydraulic pressure test to verify seal integrity."""
    # Standard test pressure for slave cylinders is typically around 1000-1500 psi
    pressure = state.get("input", {}).get("requested_test_pressure", 1250)

    # Simulation: seals hold up to 2500 psi
    integrity = pressure <= 2500

    return {
        "log": [f"{UNISPSC_CODE}:perform_pressure_test(pressure={pressure}psi, integrity={integrity})"],
        "test_pressure_psi": pressure,
        "seal_integrity_verified": integrity,
    }


def certify_and_emit(state: State) -> dict[str, Any]:
    """Produces the final diagnostic report and certification status."""
    is_certified = state.get("seal_integrity_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:certify_and_emit(certified={is_certified})"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metadata": {
                "bore_diameter_mm": state.get("bore_diameter_mm"),
                "fluid_type": state.get("fluid_compatibility"),
                "max_pressure_tested_psi": state.get("test_pressure_psi"),
            },
            "ok": is_certified,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_specs)
_g.add_node("pressure_test", perform_pressure_test)
_g.add_node("certify", certify_and_emit)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "pressure_test")
_g.add_edge("pressure_test", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
