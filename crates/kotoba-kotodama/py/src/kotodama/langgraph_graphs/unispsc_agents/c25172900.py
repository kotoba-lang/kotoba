# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172900 — Lighting (segment 25).

Bespoke graph logic for lighting equipment specification and validation.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172900"
UNISPSC_TITLE = "Lighting"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172900"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    voltage_v: float
    wattage_w: float
    lumens_lm: float
    efficacy_lm_w: float
    is_compliant: bool


def analyze_request(state: State) -> dict[str, Any]:
    """Ingests and sanitizes lighting parameters from input."""
    inp = state.get("input") or {}
    voltage = float(inp.get("voltage", 120.0))
    wattage = float(inp.get("wattage", 60.0))
    lumens = float(inp.get("lumens", 800.0))

    return {
        "log": [f"{UNISPSC_CODE}:analyze_request"],
        "voltage_v": voltage,
        "wattage_w": wattage,
        "lumens_lm": lumens,
    }


def calculate_photometrics(state: State) -> dict[str, Any]:
    """Calculates luminous efficacy and energy compliance."""
    wattage = state.get("wattage_w", 1.0)
    lumens = state.get("lumens_lm", 0.0)

    # Efficiency calculation (lumens per watt)
    efficacy = lumens / max(wattage, 0.001)
    # Mock compliance: efficacy must be > 80 lm/W for modern LED standards
    compliant = efficacy > 80.0

    return {
        "log": [f"{UNISPSC_CODE}:calculate_photometrics"],
        "efficacy_lm_w": efficacy,
        "is_compliant": compliant,
    }


def generate_lighting_spec(state: State) -> dict[str, Any]:
    """Formats the final lighting specification output."""
    return {
        "log": [f"{UNISPSC_CODE}:generate_lighting_spec"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "analysis": {
                "efficacy_lm_w": round(state.get("efficacy_lm_w", 0.0), 2),
                "energy_compliant": state.get("is_compliant"),
                "input_voltage": state.get("voltage_v"),
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("analyze", analyze_request)
_g.add_node("calculate", calculate_photometrics)
_g.add_node("generate", generate_lighting_spec)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "calculate")
_g.add_edge("calculate", "generate")
_g.add_edge("generate", END)

graph = _g.compile()
