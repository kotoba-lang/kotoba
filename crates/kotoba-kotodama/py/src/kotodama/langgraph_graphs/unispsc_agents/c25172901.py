# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172901 — Lighting (segment 25).

Bespoke graph logic for vehicle lighting components, ensuring voltage
compatibility, luminance standards, and safety certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172901"
UNISPSC_TITLE = "Lighting"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172901"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    voltage_v: float
    candela_output: int
    color_temp_k: int
    is_compliant: bool


def calibrate_optical_sensor(state: State) -> dict[str, Any]:
    """Extracts optical parameters from the input payload."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:calibrate_optical_sensor"],
        "voltage_v": float(inp.get("voltage", 12.0)),
        "candela_output": int(inp.get("candela", 1500)),
        "color_temp_k": int(inp.get("kelvin", 5000)),
    }


def validate_luminance_standards(state: State) -> dict[str, Any]:
    """Checks if the lighting fixture meets safety and luminance thresholds."""
    candela = state.get("candela_output", 0)
    voltage = state.get("voltage_v", 0.0)

    # Lighting logic: Requires minimum candela and standard automotive voltage
    meets_standards = candela >= 1000 and voltage in [12.0, 24.0, 48.0]

    return {
        "log": [f"{UNISPSC_CODE}:validate_luminance_standards"],
        "is_compliant": meets_standards,
    }


def certify_fixture(state: State) -> dict[str, Any]:
    """Finalizes the lighting manifest with certification status."""
    is_compliant = state.get("is_compliant", False)
    return {
        "log": [f"{UNISPSC_CODE}:certify_fixture"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certification": "FMVSS_108_CERTIFIED" if is_compliant else "PENDING_RECALIBRATION",
            "active": is_compliant,
        },
    }


_g = StateGraph(State)

_g.add_node("calibrate_optical_sensor", calibrate_optical_sensor)
_g.add_node("validate_luminance_standards", validate_luminance_standards)
_g.add_node("certify_fixture", certify_fixture)

_g.add_edge(START, "calibrate_optical_sensor")
_g.add_edge("calibrate_optical_sensor", "validate_luminance_standards")
_g.add_edge("validate_luminance_standards", "certify_fixture")
_g.add_edge("certify_fixture", END)

graph = _g.compile()
