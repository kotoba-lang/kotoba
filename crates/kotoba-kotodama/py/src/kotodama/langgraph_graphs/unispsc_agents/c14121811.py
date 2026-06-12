# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14121811"
UNISPSC_TITLE = "Adhesion"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14121811"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    surface_energy_dyne: float
    bond_classification: str
    application_temp_c: float
    cure_duration_sec: int


def evaluate_surface(state: State) -> dict[str, Any]:
    """Analyze the substrate surface energy for adhesive compatibility."""
    inp = state.get("input") or {}
    material = str(inp.get("material", "generic_paper"))

    # Heuristic for surface energy in dynes/cm
    # High surface energy (>36) promotes better wetting and adhesion.
    energy = 38.0 if "paper" in material.lower() else 30.0
    return {
        "log": [f"{UNISPSC_CODE}:evaluate_surface:{material}"],
        "surface_energy_dyne": energy,
    }


def determine_bond_profile(state: State) -> dict[str, Any]:
    """Calculate application parameters based on surface energy."""
    energy = state.get("surface_energy_dyne", 0.0)

    # Determine classification and curing requirements
    if energy >= 36.0:
        classification = "primary_bond"
        temp = 22.5
        cure = 60
    else:
        classification = "secondary_bond"
        temp = 25.0
        cure = 180

    return {
        "log": [f"{UNISPSC_CODE}:determine_bond_profile:{classification}"],
        "bond_classification": classification,
        "application_temp_c": temp,
        "cure_duration_sec": cure,
    }


def finalize_adhesion_spec(state: State) -> dict[str, Any]:
    """Emit the final technical specification for adhesion."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_adhesion_spec"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specs": {
                "surface_energy_dyne": state.get("surface_energy_dyne"),
                "bond_grade": state.get("bond_classification"),
                "temp_c": state.get("application_temp_c"),
                "cure_sec": state.get("cure_duration_sec"),
            },
            "status": "validated",
        },
    }


_g = StateGraph(State)
_g.add_node("evaluate_surface", evaluate_surface)
_g.add_node("determine_bond_profile", determine_bond_profile)
_g.add_node("finalize_adhesion_spec", finalize_adhesion_spec)

_g.add_edge(START, "evaluate_surface")
_g.add_edge("evaluate_surface", "determine_bond_profile")
_g.add_edge("determine_bond_profile", "finalize_adhesion_spec")
_g.add_edge("finalize_adhesion_spec", END)

graph = _g.compile()
