# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23153020 — Controller.
Bespoke logic for industrial process control monitoring and signal processing.
"""

import operator
from typing import Annotated, Any, TypedDict
from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23153020"
UNISPSC_TITLE = "Controller"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23153020"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for an industrial Controller
    system_status: str
    process_variable: float
    setpoint: float
    control_output: float
    safety_interlock: bool


def scan_telemetry(state: State) -> dict[str, Any]:
    """Simulates scanning industrial telemetry and control setpoints."""
    inp = state.get("input") or {}
    pv = float(inp.get("pv", 0.0))
    sp = float(inp.get("sp", 0.0))
    interlock = bool(inp.get("interlock", False))

    return {
        "log": [f"{UNISPSC_CODE}:scan_telemetry -> PV={pv}, SP={sp}"],
        "process_variable": pv,
        "setpoint": sp,
        "safety_interlock": interlock,
        "system_status": "INITIALIZING",
    }


def solve_pid_logic(state: State) -> dict[str, Any]:
    """Computes a proportional-integral-derivative control response."""
    pv = state.get("process_variable", 0.0)
    sp = state.get("setpoint", 0.0)
    interlock = state.get("safety_interlock", False)

    if interlock:
        return {
            "log": [f"{UNISPSC_CODE}:solve_pid_logic -> INTERLOCK TRIPPED"],
            "control_output": 0.0,
            "system_status": "EMERGENCY_STOP",
        }

    error = sp - pv
    # Simple P-control implementation for simulation
    kp = 1.2
    output = error * kp

    return {
        "log": [
            f"{UNISPSC_CODE}:solve_pid_logic -> Error={error:.2f}, Output={output:.2f}"
        ],
        "control_output": output,
        "system_status": "RUNNING",
    }


def dispatch_command(state: State) -> dict[str, Any]:
    """Finalizes the control command to be sent to industrial actuators."""
    return {
        "log": [f"{UNISPSC_CODE}:dispatch_command"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": state.get("system_status"),
            "mv": state.get("control_output"),  # Manipulated Variable
            "safe": not state.get("safety_interlock"),
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("scan", scan_telemetry)
_g.add_node("solve", solve_pid_logic)
_g.add_node("dispatch", dispatch_command)

_g.add_edge(START, "scan")
_g.add_edge("scan", "solve")
_g.add_edge("solve", "dispatch")
_g.add_edge("dispatch", END)

graph = _g.compile()
