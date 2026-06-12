# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23271600"
UNISPSC_TITLE = "Soldering"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23271600"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    alloy_spec: str
    temperature_c: int
    flux_type: str
    joint_integrity_verified: bool


def configure_parameters(state: State) -> dict[str, Any]:
    """Initialize soldering station parameters from input specifications."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:configure_parameters"],
        "alloy_spec": inp.get("alloy", "Sn63Pb37"),
        "temperature_c": inp.get("temp", 360),
        "flux_type": inp.get("flux", "Rosin Activated"),
    }


def perform_soldering(state: State) -> dict[str, Any]:
    """Execute the soldering process and verify thermal adherence."""
    temp = state.get("temperature_c", 0)
    alloy = state.get("alloy_spec", "")

    # Logic: Lead-free needs higher temp, eutectic leaded is lower
    if "Pb" in alloy:
        verified = 300 <= temp <= 400
    else:
        verified = 350 <= temp <= 450

    return {
        "log": [f"{UNISPSC_CODE}:perform_soldering"],
        "joint_integrity_verified": verified,
    }


def validate_and_emit(state: State) -> dict[str, Any]:
    """Final inspection of the solder joint and result generation."""
    is_ok = state.get("joint_integrity_verified", False)
    return {
        "log": [f"{UNISPSC_CODE}:validate_and_emit"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "process_metadata": {
                "alloy": state.get("alloy_spec"),
                "temp_c": state.get("temperature_c"),
                "flux": state.get("flux_type"),
            },
            "inspection_passed": is_ok,
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("configure_parameters", configure_parameters)
_g.add_node("perform_soldering", perform_soldering)
_g.add_node("validate_and_emit", validate_and_emit)

_g.add_edge(START, "configure_parameters")
_g.add_edge("configure_parameters", "perform_soldering")
_g.add_edge("perform_soldering", "validate_and_emit")
_g.add_edge("validate_and_emit", END)

graph = _g.compile()
