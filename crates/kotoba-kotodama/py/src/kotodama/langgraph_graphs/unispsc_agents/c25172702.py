# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172702 — Space Env (segment 25).

Bespoke graph for managing space environment control systems, including
vacuum maintenance, radiation shielding analysis, and thermal stabilization.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172702"
UNISPSC_TITLE = "Space Env"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172702"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    vacuum_psi: float
    radiation_mrem: float
    thermal_k: float
    shielding_active: bool
    nominal_status: bool


def ingest_telemetry(state: State) -> dict[str, Any]:
    """Sample environmental sensors and update internal state."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:ingest_telemetry"],
        "vacuum_psi": float(inp.get("vacuum", 14.7)),
        "radiation_mrem": float(inp.get("radiation", 0.12)),
        "thermal_k": float(inp.get("thermal", 295.0)),
        "shielding_active": bool(inp.get("shielding", True)),
    }


def analyze_habitability(state: State) -> dict[str, Any]:
    """Determine if environment is within safe operating parameters."""
    vacuum = state.get("vacuum_psi", 0.0)
    radiation = state.get("radiation_mrem", 0.0)
    shielding = state.get("shielding_active", False)

    # Simple heuristic for life support health
    is_safe = (vacuum > 12.0) and (radiation < 50.0) and shielding

    return {
        "log": [f"{UNISPSC_CODE}:analyze_habitability"],
        "nominal_status": is_safe,
    }


def update_environmental_controls(state: State) -> dict[str, Any]:
    """Finalize environmental report and signal system health."""
    nominal = state.get("nominal_status", False)
    return {
        "log": [f"{UNISPSC_CODE}:update_environmental_controls"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "NOMINAL" if nominal else "DEGRADED",
            "vacuum_psi": state.get("vacuum_psi"),
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("ingest_telemetry", ingest_telemetry)
_g.add_node("analyze_habitability", analyze_habitability)
_g.add_node("update_environmental_controls", update_environmental_controls)

_g.add_edge(START, "ingest_telemetry")
_g.add_edge("ingest_telemetry", "analyze_habitability")
_g.add_edge("analyze_habitability", "update_environmental_controls")
_g.add_edge("update_environmental_controls", END)

graph = _g.compile()
