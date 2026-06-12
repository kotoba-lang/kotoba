# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12163300 — Wafer (segment 12).

Bespoke logic for managing chemical properties and specifications of
semiconductor wafers within the chemical materials segment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12163300"
UNISPSC_TITLE = "Wafer"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12163300"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific fields for Wafer
    substrate_material: str
    thickness_microns: float
    doping_agent: str
    purity_level: str
    surface_state: str


def validate_material(state: State) -> dict[str, Any]:
    """Validates the input material specifications for the wafer."""
    inp = state.get("input") or {}
    material = inp.get("material", "Silicon (Mono-crystalline)")
    thickness = float(inp.get("thickness", 775.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_material"],
        "substrate_material": material,
        "thickness_microns": thickness,
        "surface_state": "raw"
    }


def apply_chemical_doping(state: State) -> dict[str, Any]:
    """Simulates the chemical doping process to achieve desired resistivity."""
    inp = state.get("input") or {}
    dopant = inp.get("dopant", "Phosphorus (N-type)")
    purity = inp.get("purity", "9N (99.9999999%)")

    return {
        "log": [f"{UNISPSC_CODE}:apply_chemical_doping"],
        "doping_agent": dopant,
        "purity_level": purity,
        "surface_state": "doped"
    }


def finalize_wafer_spec(state: State) -> dict[str, Any]:
    """Finalizes the wafer specification and emits the resulting actor state."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_wafer_spec"],
        "surface_state": "polished",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specification": {
                "material": state.get("substrate_material"),
                "thickness": f"{state.get('thickness_microns')} um",
                "doping": state.get("doping_agent"),
                "purity": state.get("purity_level"),
                "state": "polished"
            },
            "ok": True
        }
    }


_g = StateGraph(State)
_g.add_node("validate_material", validate_material)
_g.add_node("apply_chemical_doping", apply_chemical_doping)
_g.add_node("finalize_wafer_spec", finalize_wafer_spec)

_g.add_edge(START, "validate_material")
_g.add_edge("validate_material", "apply_chemical_doping")
_g.add_edge("apply_chemical_doping", "finalize_wafer_spec")
_g.add_edge("finalize_wafer_spec", END)

graph = _g.compile()
