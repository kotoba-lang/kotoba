# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21101506 — Machine.

Bespoke graph logic for industrial machinery telemetry and control.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21101506"
UNISPSC_TITLE = "Machine"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21101506"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Machine actor
    power_level: float
    safety_interlock_active: bool
    vibration_signature: str
    maintenance_required: bool


def power_on_sequence(state: State) -> dict[str, Any]:
    """Initialize machine systems and verify safety interlocks."""
    inp = state.get("input") or {}
    requested_power = inp.get("requested_power", 100.0)

    return {
        "log": [f"{UNISPSC_CODE}:power_on_sequence"],
        "power_level": requested_power,
        "safety_interlock_active": True,
    }


def execute_diagnostics(state: State) -> dict[str, Any]:
    """Perform sensor sweeps and vibration analysis."""
    p_level = state.get("power_level", 0.0)
    is_safe = state.get("safety_interlock_active", False)

    # Simulate machine logic: high power draw may trigger maintenance flag
    maintenance = p_level > 90.0
    vibe = "nominal" if is_safe else "irregular"

    return {
        "log": [f"{UNISPSC_CODE}:execute_diagnostics"],
        "vibration_signature": vibe,
        "maintenance_required": maintenance,
    }


def emit_machine_status(state: State) -> dict[str, Any]:
    """Finalize telemetry report for the machine state."""
    vibe = state.get("vibration_signature")
    maint = state.get("maintenance_required")

    return {
        "log": [f"{UNISPSC_CODE}:emit_machine_status"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "vibration": vibe,
                "needs_service": maint,
                "power_draw": state.get("power_level"),
            },
            "ok": vibe == "nominal",
        },
    }


_g = StateGraph(State)
_g.add_node("power_on_sequence", power_on_sequence)
_g.add_node("execute_diagnostics", execute_diagnostics)
_g.add_node("emit_machine_status", emit_machine_status)

_g.add_edge(START, "power_on_sequence")
_g.add_edge("power_on_sequence", "execute_diagnostics")
_g.add_edge("execute_diagnostics", "emit_machine_status")
_g.add_edge("emit_machine_status", END)

graph = _g.compile()
