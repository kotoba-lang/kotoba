# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25201710"
UNISPSC_TITLE = "Waveguide"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25201710"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    operating_frequency_ghz: float
    waveguide_standard: str
    material_composition: str
    attenuation_db_per_m: float


def validate_rf_specs(state: State) -> dict[str, Any]:
    """Evaluate input RF specifications to determine the appropriate waveguide standard."""
    inp = state.get("input") or {}
    freq = float(inp.get("freq", 10.0))

    # Simple logic to map frequency to standard (WR-XX)
    if freq >= 26.5:
        std = "WR-28"
    elif freq >= 18.0:
        std = "WR-42"
    elif freq >= 12.4:
        std = "WR-62"
    elif freq >= 8.2:
        std = "WR-90"
    else:
        std = "WR-137"

    return {
        "log": [f"{UNISPSC_CODE}:validate_rf_specs"],
        "operating_frequency_ghz": freq,
        "waveguide_standard": std,
    }


def optimize_material_propagation(state: State) -> dict[str, Any]:
    """Determine material composition and calculate estimated attenuation."""
    std = state.get("waveguide_standard", "WR-90")
    material = "Silver-plated Brass" if "WR-2" in std else "Oxygen-Free Copper"

    # Heuristic attenuation calculation
    attenuation = 0.05 if material == "Oxygen-Free Copper" else 0.08

    return {
        "log": [f"{UNISPSC_CODE}:optimize_material_propagation"],
        "material_composition": material,
        "attenuation_db_per_m": attenuation,
    }


def generate_waveguide_manifest(state: State) -> dict[str, Any]:
    """Finalize the component state and emit the architectural result."""
    return {
        "log": [f"{UNISPSC_CODE}:generate_waveguide_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "waveguide_config": {
                "standard": state.get("waveguide_standard"),
                "freq_ghz": state.get("operating_frequency_ghz"),
                "material": state.get("material_composition"),
                "loss_estimate": state.get("attenuation_db_per_m"),
            },
            "compliance": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_rf_specs)
_g.add_node("optimize", optimize_material_propagation)
_g.add_node("manifest", generate_waveguide_manifest)

_g.add_edge(START, "validate")
_g.add_edge("validate", "optimize")
_g.add_edge("optimize", "manifest")
_g.add_edge("manifest", END)

graph = _g.compile()
