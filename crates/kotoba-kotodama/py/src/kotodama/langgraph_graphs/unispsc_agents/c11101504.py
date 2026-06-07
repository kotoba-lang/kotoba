# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11101504 — Composite.
Specialized logic for nonferrous metal composite material analysis and specification.
"""

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11101504"
UNISPSC_TITLE = "Composite"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11101504"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Metal Matrix Composites (MMC)
    matrix_alloy: str
    reinforcement_phase: str
    volume_fraction: float
    theoretical_density: float
    integrity_verified: bool


def analyze_composition(state: State) -> dict[str, Any]:
    """Extracts and validates the constituent materials of the composite."""
    inp = state.get("input") or {}
    matrix = inp.get("matrix", "Aluminum 6061")
    reinforcement = inp.get("reinforcement", "Silicon Carbide (SiC)")
    vol_frac = float(inp.get("volume_fraction", 0.15))

    return {
        "log": [f"{UNISPSC_CODE}:analyze_composition"],
        "matrix_alloy": matrix,
        "reinforcement_phase": reinforcement,
        "volume_fraction": vol_frac,
        "integrity_verified": vol_frac > 0 and vol_frac < 1.0
    }


def estimate_density(state: State) -> dict[str, Any]:
    """Calculates theoretical density using the rule of mixtures."""
    # Simplified mock values for density (g/cm3)
    # Al: ~2.7, SiC: ~3.2
    v_f = state.get("volume_fraction", 0.0)
    rho_m = 2.70
    rho_r = 3.21

    density = (rho_m * (1 - v_f)) + (rho_r * v_f)

    return {
        "log": [f"{UNISPSC_CODE}:estimate_density"],
        "theoretical_density": round(density, 3)
    }


def finalize_material_data(state: State) -> dict[str, Any]:
    """Compiles the final composite material specification."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_material_data"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specifications": {
                "matrix": state.get("matrix_alloy"),
                "reinforcement": state.get("reinforcement_phase"),
                "volume_fraction": f"{state.get('volume_fraction'):.1%}",
                "theoretical_density_g_cm3": state.get("theoretical_density"),
            },
            "status": "VALIDATED" if state.get("integrity_verified") else "INVALID_COMPOSITION",
            "ok": state.get("integrity_verified", False),
        },
    }


_g = StateGraph(State)
_g.add_node("analyze", analyze_composition)
_g.add_node("estimate", estimate_density)
_g.add_node("finalize", finalize_material_data)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "estimate")
_g.add_edge("estimate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
