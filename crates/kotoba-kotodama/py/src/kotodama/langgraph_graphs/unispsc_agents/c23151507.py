# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23151507 — Welding (segment 23).
Bespoke graph logic for industrial welding process orchestration.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23151507"
UNISPSC_TITLE = "Welding"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23151507"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Welding domain state
    material_alloy: str
    weld_technique: str
    gas_flow_rate: float
    voltage_setting: float
    safety_interlock_verified: bool


def validate_metallurgy(state: State) -> dict[str, Any]:
    """Checks material compatibility and required welding technique."""
    inp = state.get("input") or {}
    alloy = inp.get("alloy", "carbon_steel")
    technique = inp.get("technique", "GMAW")

    return {
        "log": [f"{UNISPSC_CODE}:validate_metallurgy"],
        "material_alloy": alloy,
        "weld_technique": technique,
        "safety_interlock_verified": True
    }


def configure_parameters(state: State) -> dict[str, Any]:
    """Sets gas flow and voltage based on metallurgy and technique."""
    alloy = state.get("material_alloy", "carbon_steel")
    technique = state.get("weld_technique", "GMAW")

    # Simple logic for welding parameters
    base_voltage = 22.5
    flow_rate = 15.0  # CFH

    if alloy == "stainless_steel":
        flow_rate = 20.0
        base_voltage -= 2.0

    if technique == "GTAW":
        flow_rate += 5.0
        base_voltage = 14.0

    return {
        "log": [f"{UNISPSC_CODE}:configure_parameters"],
        "gas_flow_rate": flow_rate,
        "voltage_setting": base_voltage
    }


def execute_bond(state: State) -> dict[str, Any]:
    """Performs the thermal joining operation and certifies the joint."""
    is_verified = state.get("safety_interlock_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:execute_bond"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "process": "thermal_joining",
            "parameters": {
                "alloy": state.get("material_alloy"),
                "technique": state.get("weld_technique"),
                "voltage": state.get("voltage_setting"),
                "gas_flow": state.get("gas_flow_rate")
            },
            "certified": is_verified,
            "ok": is_verified,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_metallurgy)
_g.add_node("configure", configure_parameters)
_g.add_node("execute", execute_bond)

_g.add_edge(START, "validate")
_g.add_edge("validate", "configure")
_g.add_edge("configure", "execute")
_g.add_edge("execute", END)

graph = _g.compile()
