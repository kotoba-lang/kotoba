# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11161700"
UNISPSC_TITLE = "Liquid Material"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11161700"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific state for Liquid Material
    volume_m3: float
    viscosity_pa_s: float
    density_kg_m3: float
    is_flammable: bool
    temperature_k: float


def validate_fluid_properties(state: State) -> dict[str, Any]:
    """Validate physical properties of the liquid material batch."""
    inp = state.get("input") or {}
    vol = float(inp.get("volume", 0.0))
    visc = float(inp.get("viscosity", 0.001))  # Default to water-like Pa·s
    dens = float(inp.get("density", 1000.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_properties:vol={vol}"],
        "volume_m3": vol,
        "viscosity_pa_s": visc,
        "density_kg_m3": dens,
    }


def assess_safety_hazards(state: State) -> dict[str, Any]:
    """Assess safety requirements and thermal state of the liquid."""
    inp = state.get("input") or {}
    flammable = bool(inp.get("flammable", False))
    temp_c = float(inp.get("temp_c", 25.0))
    temp_k = temp_c + 273.15  # Thermodynamic baseline

    return {
        "log": [f"{UNISPSC_CODE}:assess_hazards:flammable={flammable}"],
        "is_flammable": flammable,
        "temperature_k": temp_k,
    }


def finalize_liquid_record(state: State) -> dict[str, Any]:
    """Finalize the material state for the actor registry and inventory."""
    vol = state.get("volume_m3", 0.0)
    is_flammable = state.get("is_flammable", False)
    # Simple logic: large volumes of flammable liquids require extra clearance
    safety_clearance = not is_flammable or vol < 500.0

    return {
        "log": [f"{UNISPSC_CODE}:finalize_record:clearance={safety_clearance}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "net_volume_m3": vol,
            "safety_clearance": safety_clearance,
            "uom": "cubic_meter",
            "status": "processed",
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_fluid_properties)
_g.add_node("assess", assess_safety_hazards)
_g.add_node("finalize", finalize_liquid_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "assess")
_g.add_edge("assess", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
