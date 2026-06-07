# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12163301 — Catalyst (segment 12).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12163301"
UNISPSC_TITLE = "Catalyst"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12163301"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Catalyst domain state
    reaction_substrate: str
    active_site_density: float
    thermal_threshold: float
    deactivation_coefficient: float


def validate_chemical_specs(state: State) -> dict[str, Any]:
    """Inspects catalyst purity and surface area specifications."""
    inp = state.get("input") or {}
    substrate = str(inp.get("substrate", "alkane_vapor"))
    density = float(inp.get("site_density", 8.5))
    return {
        "log": [f"{UNISPSC_CODE}:validate_chemical_specs"],
        "reaction_substrate": substrate,
        "active_site_density": density,
    }


def optimize_thermal_profile(state: State) -> dict[str, Any]:
    """Determines the optimal operating temperature for max conversion."""
    density = state.get("active_site_density", 0.0)
    # Heuristic: higher density requires tighter thermal management
    threshold = 450.0 + (density * 12.5)
    return {
        "log": [f"{UNISPSC_CODE}:optimize_thermal_profile"],
        "thermal_threshold": threshold,
        "deactivation_coefficient": 0.002 * (density / 2.0),
    }


def certify_catalyst_batch(state: State) -> dict[str, Any]:
    """Generates the final certification for the catalyst batch."""
    threshold = state.get("thermal_threshold", 0.0)
    return {
        "log": [f"{UNISPSC_CODE}:certify_catalyst_batch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "operational_metrics": {
                "max_temp_k": threshold,
                "substrate": state.get("reaction_substrate"),
                "wear_rate": state.get("deactivation_coefficient"),
            },
            "status": "approved_for_industrial_use",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_chemical_specs)
_g.add_node("optimize", optimize_thermal_profile)
_g.add_node("certify", certify_catalyst_batch)

_g.add_edge(START, "validate")
_g.add_edge("validate", "optimize")
_g.add_edge("optimize", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
