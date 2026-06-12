# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101206 — Motor (segment 26).

Bespoke logic for Power Generation and Distribution: Motor components.
This agent handles specifications validation, efficiency assessment, and
component finalization for industrial motors.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101206"
UNISPSC_TITLE = "Motor"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101206"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Motor
    specs_validated: bool
    efficiency_rating: float
    voltage_match: bool
    motor_type: str
    maintenance_interval_hours: int


def validate_specs(state: State) -> dict[str, Any]:
    inp = state.get("input") or {}
    voltage = inp.get("voltage", 0)
    m_type = inp.get("type", "AC Induction")

    # Industrial range check (e.g., 110V to 600V)
    is_standard = 110 <= voltage <= 600

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "specs_validated": True,
        "voltage_match": is_standard,
        "motor_type": m_type
    }


def assess_efficiency(state: State) -> dict[str, Any]:
    inp = state.get("input") or {}
    rpm = inp.get("rpm", 0)
    torque = inp.get("torque", 0)

    # Simplified efficiency calculation (Power Out / Power In proxy)
    # Using dummy thresholds for bespoke logic demonstration
    efficiency = 0.0
    if rpm > 0 and torque > 0:
        efficiency = min(0.975, (rpm * torque) / 9550 / (inp.get("kw_input", 1) or 1))

    return {
        "log": [f"{UNISPSC_CODE}:assess_efficiency"],
        "efficiency_rating": round(max(efficiency, 0.85), 3),
        "maintenance_interval_hours": 8000 if efficiency > 0.9 else 5000
    }


def finalize_motor_data(state: State) -> dict[str, Any]:
    valid = state.get("specs_validated", False)
    eff = state.get("efficiency_rating", 0.0)
    m_type = state.get("motor_type", "N/A")
    maint = state.get("maintenance_interval_hours", 0)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_motor_data"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metadata": {
                "motor_type": m_type,
                "efficiency_class": "IE3" if eff > 0.92 else "IE2",
                "recommended_maintenance_hrs": maint
            },
            "ok": valid and state.get("voltage_match", False)
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specs", validate_specs)
_g.add_node("assess_efficiency", assess_efficiency)
_g.add_node("finalize_motor_data", finalize_motor_data)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "assess_efficiency")
_g.add_edge("assess_efficiency", "finalize_motor_data")
_g.add_edge("finalize_motor_data", END)

graph = _g.compile()
