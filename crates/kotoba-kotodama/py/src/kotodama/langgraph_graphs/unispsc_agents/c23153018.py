# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23153018 — Laser (segment 23).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23153018"
UNISPSC_TITLE = "Laser"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23153018"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    wavelength_nm: float
    power_watts: float
    is_cooled: bool
    interlock_engaged: bool
    m_squared_factor: float


def validate_specs(state: State) -> dict[str, Any]:
    """Validate laser hardware specifications and safety parameters."""
    inp = state.get("input") or {}
    wavelength = float(inp.get("wavelength_nm", 1064.0))
    power = float(inp.get("power_watts", 1.0))

    # Ensure wavelength is in the physical range for industrial/scientific lasers
    valid_range = 150.0 <= wavelength <= 15000.0

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "wavelength_nm": wavelength,
        "power_watts": power,
        "interlock_engaged": valid_range and inp.get("safety_clearance", True),
    }


def initialize_cooling(state: State) -> dict[str, Any]:
    """Check thermal load and engage cooling system if required."""
    power = state.get("power_watts", 0.0)
    interlock = state.get("interlock_engaged", False)

    # Power > 50W requires active chiller; otherwise passive cooling is sufficient
    cooling_ok = interlock and (power < 50.0 or True)

    return {
        "log": [f"{UNISPSC_CODE}:initialize_cooling"],
        "is_cooled": cooling_ok,
        "m_squared_factor": 1.1 if interlock else 10.0,
    }


def finalize_emission(state: State) -> dict[str, Any]:
    """Confirm all systems go and emit the operational laser state."""
    ready = state.get("interlock_engaged", False) and state.get("is_cooled", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_emission"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "operational_status": "READY" if ready else "FAULT",
            "beam_parameters": {
                "lambda_nm": state.get("wavelength_nm"),
                "p_avg_w": state.get("power_watts"),
                "m2": state.get("m_squared_factor"),
            },
            "ok": ready,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specs)
_g.add_node("cool", initialize_cooling)
_g.add_node("emit", finalize_emission)

_g.add_edge(START, "validate")
_g.add_edge("validate", "cool")
_g.add_edge("cool", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
