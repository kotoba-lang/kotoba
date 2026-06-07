# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c15121523 — Pipeline.

Bespoke graph logic for pipeline management and monitoring, handling
integrity checks, flow regulation, and status reporting within the
Etz Hayyim actor substrate.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "15121523"
UNISPSC_TITLE = "Pipeline"
UNISPSC_SEGMENT = "15"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c15121523"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Pipeline
    pressure_psi: float
    flow_status: str
    leak_check_passed: bool
    maintenance_required: bool
    segment_integrity: float


def inspect_integrity(state: State) -> dict[str, Any]:
    """Inspects the physical integrity of the pipeline segment."""
    inp = state.get("input") or {}
    pressure = float(inp.get("pressure", 0.0))
    integrity = float(inp.get("integrity", 1.0))

    # Simple logic: high pressure or low integrity score fails check
    is_safe = pressure < 1200.0 and integrity > 0.85

    return {
        "log": [f"{UNISPSC_CODE}:inspect_integrity"],
        "pressure_psi": pressure,
        "segment_integrity": integrity,
        "leak_check_passed": is_safe,
    }


def regulate_flow(state: State) -> dict[str, Any]:
    """Regulates flow based on safety inspection results."""
    is_safe = state.get("leak_check_passed", False)

    if is_safe:
        status = "nominal_flow"
        maint = False
    else:
        status = "emergency_shutdown"
        maint = True

    return {
        "log": [f"{UNISPSC_CODE}:regulate_flow"],
        "flow_status": status,
        "maintenance_required": maint,
    }


def finalize_report(state: State) -> dict[str, Any]:
    """Finalizes the pipeline status report and emits result."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "pressure": state.get("pressure_psi"),
                "flow": state.get("flow_status"),
                "maint": state.get("maintenance_required"),
            },
            "ok": state.get("leak_check_passed", False),
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_integrity", inspect_integrity)
_g.add_node("regulate_flow", regulate_flow)
_g.add_node("finalize_report", finalize_report)

_g.add_edge(START, "inspect_integrity")
_g.add_edge("inspect_integrity", "regulate_flow")
_g.add_edge("regulate_flow", "finalize_report")
_g.add_edge("finalize_report", END)

graph = _g.compile()
