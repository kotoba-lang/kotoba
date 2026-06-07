# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11111802 — Nitrogen (segment 11).

Bespoke graph logic for Nitrogen production and certification.
This agent simulates the extraction, purification, and phase control
of Nitrogen (UNISPSC 11111802) for industrial and laboratory use.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11111802"
UNISPSC_TITLE = "Nitrogen"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11111802"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Nitrogen
    purity_level: float
    storage_pressure_psi: float
    phase: str  # 'gas' or 'liquid'
    flow_rate_scfh: float


def intake_and_extraction(state: State) -> dict[str, Any]:
    """Simulates the intake of atmospheric air and initial N2 extraction."""
    inp = state.get("input") or {}
    requested_phase = inp.get("phase", "gas")
    initial_purity = 0.78  # Atmospheric baseline

    return {
        "log": [f"{UNISPSC_CODE}:intake_extraction"],
        "phase": requested_phase,
        "purity_level": initial_purity,
        "flow_rate_scfh": float(inp.get("volume", 100.0))
    }


def purification_process(state: State) -> dict[str, Any]:
    """Simulates Pressure Swing Adsorption (PSA) to reach high purity."""
    current_purity = state.get("purity_level", 0.78)
    # Target 99.9% purity for high-grade nitrogen
    final_purity = max(current_purity, 0.999)

    return {
        "log": [f"{UNISPSC_CODE}:purification_psa"],
        "purity_level": final_purity
    }


def compression_and_bottling(state: State) -> dict[str, Any]:
    """Final phase adjustment and storage pressure calculation."""
    is_liquid = state.get("phase") == "liquid"
    pressure = 2500.0 if not is_liquid else 22.0  # Gas cylinders vs Cryogenic dewar

    return {
        "log": [f"{UNISPSC_CODE}:compression_bottling"],
        "storage_pressure_psi": pressure,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "purity": f"{state.get('purity_level', 0.0) * 100:.3f}%",
            "phase": state.get("phase"),
            "pressure": f"{pressure} PSI",
            "did": UNISPSC_DID,
            "status": "Certified"
        }
    }


_g = StateGraph(State)

_g.add_node("intake", intake_and_extraction)
_g.add_node("purify", purification_process)
_g.add_node("package", compression_and_bottling)

_g.add_edge(START, "intake")
_g.add_edge("intake", "purify")
_g.add_edge("purify", "package")
_g.add_edge("package", END)

graph = _g.compile()
