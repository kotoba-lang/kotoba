# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23261501 — F D M (segment 23).
Bespoke logic for Fused Deposition Modeling (FDM) process control within foundry operations.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23261501"
UNISPSC_TITLE = "F D M"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23261501"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Fused Deposition Modeling
    material_profile: str
    extrusion_temp_c: float
    bed_temp_c: float
    flow_rate_percent: int
    is_calibrated: bool


def configure_fdm_parameters(state: State) -> dict[str, Any]:
    """Configures extrusion and bed temperatures based on the input material profile."""
    inp = state.get("input") or {}
    profile = inp.get("material", "PLA-Industrial").upper()

    # Default parameters for common FDM materials used in foundry patterns
    config_map = {
        "PLA-INDUSTRIAL": (215.0, 60.0, 100),
        "ABS-PATTERN": (245.0, 105.0, 95),
        "PC-FOUNDRY": (270.0, 115.0, 100)
    }

    ext_t, bed_t, flow = config_map.get(profile, (210.0, 50.0, 100))

    return {
        "log": [f"{UNISPSC_CODE}:configure_fdm_parameters"],
        "material_profile": profile,
        "extrusion_temp_c": ext_t,
        "bed_temp_c": bed_t,
        "flow_rate_percent": flow
    }


def verify_thermal_stability(state: State) -> dict[str, Any]:
    """Simulates verification of nozzle and bed thermal stability before deposition."""
    ext_t = state.get("extrusion_temp_c", 0.0)
    bed_t = state.get("bed_temp_c", 0.0)

    # In a physical system, this would monitor PID loop feedback
    stability_achieved = ext_t > 0 and bed_t > 0

    return {
        "log": [f"{UNISPSC_CODE}:verify_thermal_stability"],
        "is_calibrated": stability_achieved
    }


def generate_fdm_output(state: State) -> dict[str, Any]:
    """Finalizes the FDM job state and produces the result payload."""
    return {
        "log": [f"{UNISPSC_CODE}:generate_fdm_output"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "job_status": "SUCCESS" if state.get("is_calibrated") else "FAILURE",
            "material": state.get("material_profile"),
            "settings": {
                "extrusion_temp": state.get("extrusion_temp_c"),
                "bed_temp": state.get("bed_temp_c"),
                "flow_percent": state.get("flow_rate_percent")
            }
        }
    }


_g = StateGraph(State)
_g.add_node("configure", configure_fdm_parameters)
_g.add_node("verify", verify_thermal_stability)
_g.add_node("emit", generate_fdm_output)

_g.add_edge(START, "configure")
_g.add_edge("configure", "verify")
_g.add_edge("verify", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
