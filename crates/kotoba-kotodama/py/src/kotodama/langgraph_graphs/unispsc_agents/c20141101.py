# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20141101 — Bearing (segment 20).

Bespoke logic for bearing specification verification and service life calculation.
"""

from __future__ import annotations

import operator
# No imports from langchain or external services allowed - pure Python logic
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20141101"
UNISPSC_TITLE = "Bearing"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20141101"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Bearings
    inner_diameter_mm: float
    outer_diameter_mm: float
    load_rating_kn: float
    lubrication_type: str
    estimated_life_hours: float


def verify_specs(state: State) -> dict[str, Any]:
    """Extract and verify physical bearing specifications from input."""
    inp = state.get("input") or {}
    inner = float(inp.get("inner_diameter", 0.0))
    outer = float(inp.get("outer_diameter", 0.0))
    lubrication = str(inp.get("lubrication", "standard_grease"))

    return {
        "log": [f"{UNISPSC_CODE}:verify_specs"],
        "inner_diameter_mm": inner,
        "outer_diameter_mm": outer,
        "lubrication_type": lubrication,
    }


def calculate_performance(state: State) -> dict[str, Any]:
    """Calculate estimated service life based on load conditions and specs."""
    inp = state.get("input") or {}
    load = float(inp.get("applied_load_kn", 1.0))

    # Simulated bearing L10 life calculation logic
    # Life in millions of revolutions = (C/P)^p
    # Where C is load rating, P is applied load, p is 3 for ball bearings
    base_factor = 1.0
    if state.get("lubrication_type") == "synthetic_oil":
        base_factor = 1.2

    # Dummy calculation for simulation
    est_life = (1000000.0 * base_factor) / (load**3 + 0.1)

    return {
        "log": [f"{UNISPSC_CODE}:calculate_performance"],
        "load_rating_kn": load,
        "estimated_life_hours": est_life,
    }


def finalize_report(state: State) -> dict[str, Any]:
    """Emit the final bearing technical assessment result."""
    inner = state.get("inner_diameter_mm", 0.0)
    outer = state.get("outer_diameter_mm", 0.0)
    life = state.get("estimated_life_hours", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "assessment": {
                "dimensions": f"{inner}mm x {outer}mm",
                "estimated_life_cycles": f"{life:.2f}M",
                "status": "validated" if life > 100 else "marginal",
                "ok": True,
            },
        },
    }


_g = StateGraph(State)
_g.add_node("verify_specs", verify_specs)
_g.add_node("calculate_performance", calculate_performance)
_g.add_node("finalize_report", finalize_report)

_g.add_edge(START, "verify_specs")
_g.add_edge("verify_specs", "calculate_performance")
_g.add_edge("calculate_performance", "finalize_report")
_g.add_edge("finalize_report", END)

graph = _g.compile()
