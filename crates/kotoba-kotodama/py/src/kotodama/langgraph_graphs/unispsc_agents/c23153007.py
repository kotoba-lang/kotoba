# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23153007 — Controller (segment 23).

Bespoke logic for an industrial control agent. This agent simulates a
feedback loop: sensing input signals, computing control responses, and
actuating output adjustments to maintain process stability.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23153007"
UNISPSC_TITLE = "Controller"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23153007"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra domain fields for "Controller"
    signal_input: float
    setpoint: float
    control_output: float
    error_margin: float
    is_stable: bool


def sense(state: State) -> dict[str, Any]:
    """Reads the input signal and identifies the target setpoint."""
    inp = state.get("input") or {}
    signal = float(inp.get("signal", 0.0))
    target = float(inp.get("target", 100.0))

    return {
        "log": [f"{UNISPSC_CODE}:sense -> signal={signal}, setpoint={target}"],
        "signal_input": signal,
        "setpoint": target,
    }


def compute(state: State) -> dict[str, Any]:
    """Calculates the control output based on the error between signal and setpoint."""
    signal = state.get("signal_input", 0.0)
    target = state.get("setpoint", 0.0)

    error = target - signal
    # Simple proportional control simulation (gain = 0.5)
    output = error * 0.5
    stable = abs(error) < 1.0

    return {
        "log": [f"{UNISPSC_CODE}:compute -> error={error}, output={output}"],
        "control_output": output,
        "error_margin": error,
        "is_stable": stable,
    }


def actuate(state: State) -> dict[str, Any]:
    """Finalizes the control cycle and prepares the result dictionary."""
    is_stable = state.get("is_stable", False)
    output = state.get("control_output", 0.0)

    status = "STABLE" if is_stable else "CORRECTING"

    return {
        "log": [f"{UNISPSC_CODE}:actuate -> status={status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "control_status": status,
            "final_output": output,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("sense", sense)
_g.add_node("compute", compute)
_g.add_node("actuate", actuate)

_g.add_edge(START, "sense")
_g.add_edge("sense", "compute")
_g.add_edge("compute", "actuate")
_g.add_edge("actuate", END)

graph = _g.compile()
