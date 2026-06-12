# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111905"
UNISPSC_TITLE = "Ballast"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111905"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    lamp_compatibility: str
    input_voltage_range: tuple[int, int]
    power_factor: float
    thermal_protection_enabled: bool
    is_compliant: bool


def inspect_electrical_specs(state: State) -> dict[str, Any]:
    """Analyzes input for ballast electrical requirements and lamp compatibility."""
    inp = state.get("input") or {}
    lamp = inp.get("lamp_type", "HID")
    min_v = inp.get("min_voltage", 120)
    max_v = inp.get("max_voltage", 277)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_electrical_specs"],
        "lamp_compatibility": lamp,
        "input_voltage_range": (min_v, max_v),
    }


def validate_efficiency_standards(state: State) -> dict[str, Any]:
    """Checks if the ballast meets energy efficiency and thermal safety thresholds."""
    # Simulate logic for high-efficiency ballast validation
    voltage_range = state.get("input_voltage_range", (0, 0))
    pf = 0.98 if voltage_range[1] > 200 else 0.92
    thermal = True if state.get("lamp_compatibility") != "Legacy" else False

    return {
        "log": [f"{UNISPSC_CODE}:validate_efficiency_standards"],
        "power_factor": pf,
        "thermal_protection_enabled": thermal,
        "is_compliant": pf >= 0.9 and thermal,
    }


def certify_ballast_payload(state: State) -> dict[str, Any]:
    """Finalizes the agent state and emits the certified ballast configuration."""
    compliant = state.get("is_compliant", False)
    return {
        "log": [f"{UNISPSC_CODE}:certify_ballast_payload"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "validation": {
                "compliant": compliant,
                "power_factor": state.get("power_factor"),
                "thermal_safety": state.get("thermal_protection_enabled"),
                "lamp_type": state.get("lamp_compatibility"),
            },
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_electrical_specs", inspect_electrical_specs)
_g.add_node("validate_efficiency_standards", validate_efficiency_standards)
_g.add_node("certify_ballast_payload", certify_ballast_payload)

_g.add_edge(START, "inspect_electrical_specs")
_g.add_edge("inspect_electrical_specs", "validate_efficiency_standards")
_g.add_edge("validate_efficiency_standards", "certify_ballast_payload")
_g.add_edge("certify_ballast_payload", END)

graph = _g.compile()
