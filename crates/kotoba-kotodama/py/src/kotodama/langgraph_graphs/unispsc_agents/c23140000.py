# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23140000 — Machine (segment 23).

Bespoke graph logic for industrial machinery tracking, health diagnostics,
and operational performance monitoring within the Etz Hayyim ecosystem.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23140000"
UNISPSC_TITLE = "Machine"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23140000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    serial_number: str
    runtime_hours: float
    vibration_level: float
    health_score: float
    maintenance_required: bool


def ingest_telemetry(state: State) -> dict[str, Any]:
    """Extract machine specifications and telemetry from input."""
    inp = state.get("input") or {}
    serial = str(inp.get("serial", "MCH-GEN-001"))
    hours = float(inp.get("hours", 0.0))
    vibe = float(inp.get("vibration", 0.05))

    return {
        "log": [f"{UNISPSC_CODE}:ingest_telemetry(serial={serial})"],
        "serial_number": serial,
        "runtime_hours": hours,
        "vibration_level": vibe,
    }


def analyze_health(state: State) -> dict[str, Any]:
    """Calculate machine health based on runtime and vibration levels."""
    hours = state.get("runtime_hours", 0.0)
    vibe = state.get("vibration_level", 0.0)

    # Simple logic: health degrades with hours and excessive vibration
    base_health = 100.0
    hour_penalty = (hours / 1000.0) * 2.0
    vibe_penalty = vibe * 50.0

    health = max(0.0, base_health - hour_penalty - vibe_penalty)
    needs_maint = health < 75.0 or vibe > 0.8

    return {
        "log": [f"{UNISPSC_CODE}:analyze_health(score={health:.2f})"],
        "health_score": health,
        "maintenance_required": needs_maint,
    }


def generate_manifest(state: State) -> dict[str, Any]:
    """Emit the final machine state and actor metadata."""
    health = state.get("health_score", 0.0)
    maint = state.get("maintenance_required", False)

    status = "FAULT" if health < 40 else "WARNING" if maint else "OPERATIONAL"

    return {
        "log": [f"{UNISPSC_CODE}:generate_manifest(status={status})"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "metadata": {
                "serial": state.get("serial_number"),
                "runtime": state.get("runtime_hours"),
                "health_score": round(health, 2),
                "operational_status": status,
                "maintenance_flag": maint
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("ingest_telemetry", ingest_telemetry)
_g.add_node("analyze_health", analyze_health)
_g.add_node("generate_manifest", generate_manifest)

_g.add_edge(START, "ingest_telemetry")
_g.add_edge("ingest_telemetry", "analyze_health")
_g.add_edge("analyze_health", "generate_manifest")
_g.add_edge("generate_manifest", END)

graph = _g.compile()
