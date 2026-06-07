# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24112111 — Stabilizer (segment 24).

This agent monitors and manages stabilizing equipment for material handling.
It analyzes vibration and tilt telemetry to adjust damping pressure and
ensure load integrity during transport or storage.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24112111"
UNISPSC_TITLE = "Stabilizer"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24112111"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Stabilizer equipment management
    vibration_m_s2: float
    tilt_angle_deg: float
    pressure_kpa: float
    active_damping: bool


def inspect_load(state: State) -> dict[str, Any]:
    """Analyze incoming telemetry for stability issues."""
    inp = state.get("input") or {}
    vibration = float(inp.get("vibration", 0.0))
    tilt = float(inp.get("tilt", 0.0))
    return {
        "log": [f"{UNISPSC_CODE}:inspect_load"],
        "vibration_m_s2": vibration,
        "tilt_angle_deg": tilt,
    }


def stabilize_system(state: State) -> dict[str, Any]:
    """Adjust stabilizer pressure and damping based on load analysis."""
    vibration = state.get("vibration_m_s2", 0.0)
    tilt = state.get("tilt_angle_deg", 0.0)

    # Activate damping if vibration exceeds 5.0 m/s^2 or tilt exceeds 10 degrees
    needs_damping = vibration > 5.0 or abs(tilt) > 10.0
    # Increase pressure to 250 kPa if damping is active, else maintain 101.3 kPa baseline
    pressure = 250.0 if needs_damping else 101.3

    return {
        "log": [f"{UNISPSC_CODE}:stabilize_system"],
        "pressure_kpa": pressure,
        "active_damping": needs_damping,
    }


def conclude_operation(state: State) -> dict[str, Any]:
    """Emit the final stabilization status and telemetry summary."""
    status = "STABILIZED" if state.get("active_damping") else "IDLE"
    return {
        "log": [f"{UNISPSC_CODE}:conclude_operation"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": status,
            "metrics": {
                "pressure_kpa": state.get("pressure_kpa"),
                "vibration": state.get("vibration_m_s2"),
                "damping_active": state.get("active_damping")
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_load)
_g.add_node("stabilize", stabilize_system)
_g.add_node("conclude", conclude_operation)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "stabilize")
_g.add_edge("stabilize", "conclude")
_g.add_edge("conclude", END)

graph = _g.compile()
