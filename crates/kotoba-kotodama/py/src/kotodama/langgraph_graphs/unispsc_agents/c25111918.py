# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111918 — Furler (segment 25).

Bespoke logic for managing sailboat furling system state, tension monitoring,
and deployment operations.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict, Literal

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111918"
UNISPSC_TITLE = "Furler"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111918"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Furler
    tension_newtons: float
    deployment_percentage: float
    mechanism_status: Literal["nominal", "strained", "jammed"]
    rotation_count: int


def inspect_mechanism(state: State) -> dict[str, Any]:
    """Inspects the furling mechanism and current line tension."""
    inp = state.get("input") or {}
    tension = float(inp.get("tension", 150.0))

    status: Literal["nominal", "strained", "jammed"] = "nominal"
    if tension > 600:
        status = "strained"
    if tension > 1200:
        status = "jammed"

    return {
        "log": [f"{UNISPSC_CODE}:inspect_mechanism - Tension: {tension}N, Status: {status}"],
        "tension_newtons": tension,
        "mechanism_status": status,
    }


def operate_furler(state: State) -> dict[str, Any]:
    """Updates deployment percentage based on rotation input and mechanism state."""
    inp = state.get("input") or {}
    status = state.get("mechanism_status", "nominal")
    current_deployment = state.get("deployment_percentage", 0.0)

    if status == "jammed":
        return {
            "log": [f"{UNISPSC_CODE}:operate_furler - Operation blocked: mechanism jammed"],
            "deployment_percentage": current_deployment
        }

    requested_deployment = float(inp.get("target_deployment", 0.0))

    # Strained mechanism moves slower or partially
    if status == "strained":
        new_deployment = (requested_deployment + current_deployment) / 2
        log_msg = f"Restricted deployment due to strain: {new_deployment}%"
    else:
        new_deployment = max(0.0, min(100.0, requested_deployment))
        log_msg = f"Deployment updated to {new_deployment}%"

    return {
        "log": [f"{UNISPSC_CODE}:operate_furler - {log_msg}"],
        "deployment_percentage": new_deployment,
        "rotation_count": state.get("rotation_count", 0) + 1,
    }


def emit_telemetry(state: State) -> dict[str, Any]:
    """Finalizes the agent execution and emits system telemetry."""
    status = state.get("mechanism_status", "nominal")
    deployment = state.get("deployment_percentage", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:emit_telemetry - Finalizing state"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "deployment_status": f"{deployment:.1f}%",
                "tension_load": f"{state.get('tension_newtons', 0.0)}N",
                "system_health": status,
                "cycles": state.get("rotation_count", 0),
            },
            "ok": status != "jammed",
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_mechanism)
_g.add_node("operate", operate_furler)
_g.add_node("emit", emit_telemetry)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "operate")
_g.add_edge("operate", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
