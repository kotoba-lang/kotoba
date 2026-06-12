# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111930 — Spinnaker (segment 25).
Bespoke sail-trimming logic for asymmetric and symmetric spinnaker deployment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111930"
UNISPSC_TITLE = "Spinnaker"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111930"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Spinnaker management
    wind_speed_kts: float
    sail_material: str
    is_symmetric: bool
    rigging_tension: int
    deployment_ready: bool


def inspect_gear(state: State) -> dict[str, Any]:
    """Validates the rigging and determines spinnaker configuration."""
    inp = state.get("input") or {}
    wind = float(inp.get("wind_speed", 12.0))
    # Symmetric spinnakers are typically used for deeper downwind angles
    symmetric = inp.get("angle", 180) > 150

    return {
        "log": [f"{UNISPSC_CODE}:inspect_gear"],
        "wind_speed_kts": wind,
        "is_symmetric": symmetric,
        "deployment_ready": wind < 30.0,  # Safety threshold for spinnaker use
    }


def optimize_trim(state: State) -> dict[str, Any]:
    """Calculates material requirements and tension based on wind conditions."""
    wind = state.get("wind_speed_kts", 0.0)

    # Heavy air requires Nylon 1.5oz; light air uses 0.5oz or 0.75oz
    material = "Nylon 1.5oz" if wind > 18.0 else "Nylon 0.75oz"
    tension = int(wind * 2.5)

    return {
        "log": [f"{UNISPSC_CODE}:optimize_trim"],
        "sail_material": material,
        "rigging_tension": tension,
    }


def finalize_deployment(state: State) -> dict[str, Any]:
    """Produces the final configuration for the spinnaker actor."""
    ready = state.get("deployment_ready", False)
    sym = "Symmetric" if state.get("is_symmetric") else "Asymmetric"

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "config": {
            "type": sym,
            "material": state.get("sail_material"),
            "tension_psi": state.get("rigging_tension"),
            "active": ready,
        },
        "status": "deployed" if ready else "stowed_high_wind",
    }

    return {
        "log": [f"{UNISPSC_CODE}:finalize_deployment"],
        "result": res,
    }


_g = StateGraph(State)

_g.add_node("inspect_gear", inspect_gear)
_g.add_node("optimize_trim", optimize_trim)
_g.add_node("finalize_deployment", finalize_deployment)

_g.add_edge(START, "inspect_gear")
_g.add_edge("inspect_gear", "optimize_trim")
_g.add_edge("optimize_trim", "finalize_deployment")
_g.add_edge("finalize_deployment", END)

graph = _g.compile()
