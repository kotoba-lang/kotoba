# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23153004 — Motor (segment 23).

Bespoke graph logic for industrial motor specification validation and performance analysis.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23153004"
UNISPSC_TITLE = "Motor"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23153004"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Motor actors
    voltage_rating: float
    power_output_kw: float
    rpm_nominal: int
    cooling_method: str
    is_compliant: bool


def validate_motor_specs(state: State) -> dict[str, Any]:
    """Validates the basic electrical and mechanical parameters of the motor."""
    inp = state.get("input") or {}
    voltage = float(inp.get("voltage", 0.0))
    power = float(inp.get("power", 0.0))
    rpm = int(inp.get("rpm", 0))
    cooling = str(inp.get("cooling", "Natural Air"))

    # Basic compliance check for industrial motors
    is_compliant = voltage >= 110 and power > 0 and rpm > 0

    return {
        "log": [f"{UNISPSC_CODE}:validate_motor_specs"],
        "voltage_rating": voltage,
        "power_output_kw": power,
        "rpm_nominal": rpm,
        "cooling_method": cooling,
        "is_compliant": is_compliant,
    }


def analyze_efficiency_profile(state: State) -> dict[str, Any]:
    """Mocks a calculation of the motor's efficiency profile based on specs."""
    power = state.get("power_output_kw", 0.0)
    rpm = state.get("rpm_nominal", 0)

    # Hypothetical efficiency classification (e.g. IE3 Premium Efficiency)
    efficiency_class = "IE3" if power > 0.75 and rpm > 1000 else "IE1"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_efficiency_profile"],
        "efficiency_class": efficiency_class,
    }


def finalize_catalog_entry(state: State) -> dict[str, Any]:
    """Packages the validated motor data into a standardized catalog result."""
    is_ok = state.get("is_compliant", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_catalog_entry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "voltage": state.get("voltage_rating"),
                "power_kw": state.get("power_output_kw"),
                "rpm": state.get("rpm_nominal"),
                "cooling": state.get("cooling_method"),
            },
            "status": "VALIDATED" if is_ok else "INVALID_SPECS",
            "ok": is_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_motor_specs)
_g.add_node("analyze", analyze_efficiency_profile)
_g.add_node("emit", finalize_catalog_entry)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
