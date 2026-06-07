# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23152102 — Stationary Separation (segment 23).
Bespoke logic for screen mesh validation, separation efficiency calculation, and maintenance verification.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23152102"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23152102"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Stationary Separation Equipment
    mesh_size_mm: float
    separation_efficiency: float
    maintenance_cleared: bool
    feed_material_type: str
    clog_detection_enabled: bool
    vibration_sensor_ok: bool


def inspect_hardware(state: State) -> dict[str, Any]:
    """Inspects the physical state, mesh integrity, and sensors of the stationary screen."""
    inp = state.get("input") or {}
    maintenance = inp.get("maintenance", {})
    sensors = inp.get("sensors", {})

    is_cleared = maintenance.get("status") in ["certified", "cleared", "ok"]
    vibration_ok = sensors.get("vibration", "nominal") == "nominal"

    return {
        "log": [f"{UNISPSC_CODE}:inspect_hardware"],
        "maintenance_cleared": is_cleared,
        "vibration_sensor_ok": vibration_ok,
        "mesh_size_mm": float(inp.get("mesh_size", 0.5)),
        "clog_detection_enabled": bool(sensors.get("clog_sensor_active", True)),
    }


def calculate_separation(state: State) -> dict[str, Any]:
    """Calculates separation efficiency based on hardware state and material properties."""
    if not state.get("maintenance_cleared") or not state.get("vibration_sensor_ok"):
        return {
            "log": [f"{UNISPSC_CODE}:calculate_separation:inhibited"],
            "separation_efficiency": 0.0,
        }

    mesh = state.get("mesh_size_mm", 0.5)
    # Heuristic: smaller mesh is more efficient for typical separation tasks in this class
    # but more prone to clogging if clog detection is off
    clog_factor = 1.0 if state.get("clog_detection_enabled") else 0.8
    efficiency = (0.98 if mesh < 1.0 else 0.88) * clog_factor

    return {
        "log": [f"{UNISPSC_CODE}:calculate_separation:success"],
        "separation_efficiency": round(efficiency, 3),
        "feed_material_type": state.get("input", {}).get("material", "generic_industrial"),
    }


def emit_result(state: State) -> dict[str, Any]:
    """Emits the final processing result and operational metrics."""
    efficiency = state.get("separation_efficiency", 0.0)
    is_ok = efficiency > 0.75 and state.get("maintenance_cleared", False)

    return {
        "log": [f"{UNISPSC_CODE}:emit_result"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "efficiency": efficiency,
            "material": state.get("feed_material_type"),
            "ok": is_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_hardware", inspect_hardware)
_g.add_node("calculate_separation", calculate_separation)
_g.add_node("emit_result", emit_result)

_g.add_edge(START, "inspect_hardware")
_g.add_edge("inspect_hardware", "calculate_separation")
_g.add_edge("calculate_separation", "emit_result")
_g.add_edge("emit_result", END)

graph = _g.compile()
