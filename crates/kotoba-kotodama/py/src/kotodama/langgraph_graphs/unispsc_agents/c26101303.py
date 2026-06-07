# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101303"
UNISPSC_TITLE = "Dynamotor"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101303"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Dynamotor-specific domain fields
    input_voltage_v: float
    output_voltage_v: float
    armature_rpm: int
    load_amperage: float
    thermal_compliance: bool


def configure_electrical_spec(state: State) -> dict[str, Any]:
    """Extracts and validates the electrical specification for the dynamotor."""
    inp = state.get("input") or {}
    v_in = float(inp.get("voltage_in", 24.0))
    v_out = float(inp.get("voltage_out", 400.0))
    load = float(inp.get("load_a", 0.2))

    # Basic safety check for voltage ranges
    is_safe = 6.0 <= v_in <= 48.0

    return {
        "log": [f"{UNISPSC_CODE}:configure_electrical_spec"],
        "input_voltage_v": v_in,
        "output_voltage_v": v_out,
        "load_amperage": load,
        "thermal_compliance": is_safe,
    }


def simulate_rotation(state: State) -> dict[str, Any]:
    """Simulates the electromechanical rotation behavior of the common armature."""
    v_in = state.get("input_voltage_v", 0.0)
    load = state.get("load_amperage", 0.0)

    # RPM is typically proportional to input voltage in a dynamotor
    # Heuristic: 400 RPM per volt minus load-induced drag
    base_rpm = int(v_in * 400)
    drag = int(load * 500)
    actual_rpm = max(0, base_rpm - drag)

    # Overload detection
    thermal_ok = state.get("thermal_compliance", False) and (load < 10.0)

    return {
        "log": [f"{UNISPSC_CODE}:simulate_rotation"],
        "armature_rpm": actual_rpm,
        "thermal_compliance": thermal_ok,
    }


def finalize_telemetry(state: State) -> dict[str, Any]:
    """Compiles the final operational telemetry and result for the dynamotor."""
    compliant = state.get("thermal_compliance", False)
    rpm = state.get("armature_rpm", 0)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "OPERATIONAL" if compliant and rpm > 0 else "FAULT",
            "telemetry": {
                "rpm": rpm,
                "input_v": state.get("input_voltage_v"),
                "output_v": state.get("output_voltage_v"),
                "load_a": state.get("load_amperage"),
            },
            "ok": compliant and rpm > 0,
        },
    }


_g = StateGraph(State)
_g.add_node("configure", configure_electrical_spec)
_g.add_node("simulate", simulate_rotation)
_g.add_node("finalize", finalize_telemetry)

_g.add_edge(START, "configure")
_g.add_edge("configure", "simulate")
_g.add_edge("simulate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
