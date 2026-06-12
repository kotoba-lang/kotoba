# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23231402 — Spindle (segment 23).

This bespoke graph manages the operational state of industrial spindles,
tracking rotation metrics, thermal stability, and mechanical clamping.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23231402"
UNISPSC_TITLE = "Spindle"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23231402"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Spindle mechanics
    target_rpm: int
    actual_rpm: int
    thermal_stable: bool
    clamping_pressure_psi: float


def validate_input(state: State) -> dict[str, Any]:
    """Validates the spindle operation request parameters."""
    inp = state.get("input") or {}
    target = inp.get("rpm", 5000)
    return {
        "log": [f"{UNISPSC_CODE}:validate_input"],
        "target_rpm": target,
        "clamping_pressure_psi": inp.get("pressure", 750.0)
    }


def analyze_mechanics(state: State) -> dict[str, Any]:
    """Calculates thermal stability based on target RPM and clamping pressure."""
    target = state.get("target_rpm", 0)
    # Spindles are considered thermally stable if under 10k RPM in this simulation
    is_stable = target < 10000
    return {
        "log": [f"{UNISPSC_CODE}:analyze_mechanics"],
        "thermal_stable": is_stable,
        "actual_rpm": int(target * 0.998)  # slight slippage simulation
    }


def finalize_state(state: State) -> dict[str, Any]:
    """Emits the final operational telemetry for the spindle component."""
    stable = state.get("thermal_stable", False)
    pressure = state.get("clamping_pressure_psi", 0.0)
    ok = stable and pressure > 500.0

    return {
        "log": [f"{UNISPSC_CODE}:finalize_state"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "rpm": state.get("actual_rpm"),
                "stable": stable,
                "pressure": pressure
            },
            "ok": ok,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_input)
_g.add_node("analyze", analyze_mechanics)
_g.add_node("finalize", finalize_state)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
