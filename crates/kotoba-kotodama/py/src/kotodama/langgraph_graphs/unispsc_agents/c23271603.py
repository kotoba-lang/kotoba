# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23271603 — Soldering Process (segment 23).
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23271603"
UNISPSC_TITLE = "Soldering Process"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23271603"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    target_temperature: float
    solder_alloy: str
    flux_type: str
    thermal_profile_valid: bool
    inspection_passed: bool


def setup_parameters(state: State) -> dict[str, Any]:
    """Configures the soldering environment based on the input specifications."""
    inp = state.get("input") or {}
    alloy = inp.get("alloy", "Sn96.5Ag3.0Cu0.5")
    temp = inp.get("peak_temp", 245.0)
    return {
        "log": [f"{UNISPSC_CODE}:setup: alloy={alloy}, peak={temp}C"],
        "solder_alloy": alloy,
        "target_temperature": temp,
        "flux_type": inp.get("flux", "Rosin-based"),
    }


def apply_reflow(state: State) -> dict[str, Any]:
    """Simulates the reflow soldering thermal cycle."""
    temp = state.get("target_temperature", 0.0)
    valid = temp >= 230.0 and temp <= 260.0
    return {
        "log": [f"{UNISPSC_CODE}:reflow: peak reached {temp}C, profile_valid={valid}"],
        "thermal_profile_valid": valid,
    }


def inspect_joints(state: State) -> dict[str, Any]:
    """Verifies the integrity of the soldered joints via visual simulation."""
    profile_ok = state.get("thermal_profile_valid", False)
    passed = profile_ok  # Simplified quality gate
    return {
        "log": [f"{UNISPSC_CODE}:inspect: quality {'PASS' if passed else 'FAIL'}"],
        "inspection_passed": passed,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "success": passed,
            "alloy_used": state.get("solder_alloy"),
            "process_log": "Reflow cycle complete",
        },
    }


_g = StateGraph(State)
_g.add_node("setup", setup_parameters)
_g.add_node("reflow", apply_reflow)
_g.add_node("inspect", inspect_joints)

_g.add_edge(START, "setup")
_g.add_edge("setup", "reflow")
_g.add_edge("reflow", "inspect")
_g.add_edge("inspect", END)

graph = _g.compile()
