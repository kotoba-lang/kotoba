# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12142204"
UNISPSC_TITLE = "Material"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12142204"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for agricultural fertilizer/nutrient materials
    material_viscosity: float
    granule_size_mm: float
    corrosion_risk_level: str
    application_compatibility_score: int


def inspect_material_physical_properties(state: State) -> dict[str, Any]:
    """Analyzes the physical characteristics of the material to be applied."""
    inp = state.get("input") or {}
    viscosity = float(inp.get("viscosity", 0.0))
    size = float(inp.get("size", 0.0))

    # Determine risk based on chemical properties
    risk = "high" if viscosity > 45.0 else "standard"

    return {
        "log": [f"{UNISPSC_CODE}:inspect_material_physical_properties"],
        "material_viscosity": viscosity,
        "granule_size_mm": size,
        "corrosion_risk_level": risk,
    }


def verify_machinery_compatibility(state: State) -> dict[str, Any]:
    """Checks if the material properties are compatible with the applicator machinery."""
    viscosity = state.get("material_viscosity", 0.0)
    size = state.get("granule_size_mm", 0.0)

    # Base compatibility scoring logic
    score = 100
    if viscosity > 80.0:
        score -= 30
    if size > 12.0 or size < 0.1:
        score -= 25

    return {
        "log": [f"{UNISPSC_CODE}:verify_machinery_compatibility"],
        "application_compatibility_score": score,
    }


def finalize_deployment_parameters(state: State) -> dict[str, Any]:
    """Finalizes the deployment record for the fertilizer/nutrient material."""
    score = state.get("application_compatibility_score", 0)
    is_safe = score >= 60

    return {
        "log": [f"{UNISPSC_CODE}:finalize_deployment_parameters"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "operational_status": "authorized" if is_safe else "rejected",
            "telemetry": {
                "compatibility": score,
                "risk": state.get("corrosion_risk_level"),
                "ready": is_safe
            }
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_material_physical_properties)
_g.add_node("verify", verify_machinery_compatibility)
_g.add_node("finalize", finalize_deployment_parameters)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
