# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122209 — Robot Motor (segment 20).
Bespoke logic for robot motor specification validation and performance assessment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122209"
UNISPSC_TITLE = "Robot Motor"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122209"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Robot Motor
    voltage_v: float
    torque_nm: float
    thermal_compliance: bool
    efficiency_rating: str


def validate_motor_specs(state: State) -> dict[str, Any]:
    """Validate the incoming electrical and mechanical specifications."""
    inp = state.get("input") or {}
    voltage = float(inp.get("voltage", 12.0))
    torque = float(inp.get("torque", 1.5))

    # Simple validation logic
    is_safe = 5.0 <= voltage <= 48.0 and torque < 50.0

    return {
        "log": [f"{UNISPSC_CODE}:validate_motor_specs"],
        "voltage_v": voltage,
        "torque_nm": torque,
        "thermal_compliance": is_safe
    }


def assess_performance(state: State) -> dict[str, Any]:
    """Determine the efficiency rating based on current state."""
    v = state.get("voltage_v", 0.0)
    t = state.get("torque_nm", 0.0)

    if v >= 24.0 and t >= 10.0:
        rating = "industrial_grade"
    elif v >= 12.0:
        rating = "consumer_grade"
    else:
        rating = "hobbyist_grade"

    return {
        "log": [f"{UNISPSC_CODE}:assess_performance"],
        "efficiency_rating": rating
    }


def emit_motor_data(state: State) -> dict[str, Any]:
    """Format and emit the final robot motor characteristics."""
    compliance = "PASS" if state.get("thermal_compliance") else "FAIL"

    return {
        "log": [f"{UNISPSC_CODE}:emit_motor_data"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "voltage": f"{state.get('voltage_v')}V",
                "torque": f"{state.get('torque_nm')}Nm",
                "rating": state.get("efficiency_rating"),
                "thermal_test": compliance
            },
            "ok": True
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_motor_specs)
_g.add_node("process", assess_performance)
_g.add_node("emit", emit_motor_data)

_g.add_edge(START, "validate")
_g.add_edge("validate", "process")
_g.add_edge("process", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
