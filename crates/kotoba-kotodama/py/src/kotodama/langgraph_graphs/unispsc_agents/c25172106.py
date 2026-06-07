# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172106 — Impact Graph (segment 25).

Bespoke graph logic for processing and visualizing vehicle impact data,
calculating structural integrity impacts and safety threshold violations.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172106"
UNISPSC_TITLE = "Impact Graph"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172106"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Impact Graph analysis
    impact_energy_joules: float
    structural_integrity: float
    safety_alarm_active: bool
    sensor_calibration_v: float


def capture_impact_telemetry(state: State) -> dict[str, Any]:
    """Ingests raw sensor data and calculates kinetic energy impact."""
    inp = state.get("input") or {}
    mass = float(inp.get("mass_kg", 1500.0))
    velocity = float(inp.get("velocity_ms", 0.0))
    # Kinetic Energy = 0.5 * m * v^2
    energy = 0.5 * mass * (velocity ** 2)

    return {
        "log": [f"{UNISPSC_CODE}:capture_impact_telemetry"],
        "impact_energy_joules": energy,
        "sensor_calibration_v": 5.0,
    }


def compute_structural_deformation(state: State) -> dict[str, Any]:
    """Maps impact energy to structural deformation and integrity loss."""
    energy = state.get("impact_energy_joules", 0.0)
    # Simplified linear integrity loss model for the impact graph
    loss_factor = 0.00001
    current_integrity = max(0.0, 100.0 - (energy * loss_factor))

    return {
        "log": [f"{UNISPSC_CODE}:compute_structural_deformation"],
        "structural_integrity": current_integrity,
        "safety_alarm_active": current_integrity < 70.0,
    }


def generate_impact_report(state: State) -> dict[str, Any]:
    """Finalizes the impact graph result with safety assessments."""
    return {
        "log": [f"{UNISPSC_CODE}:generate_impact_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "energy_kj": state.get("impact_energy_joules", 0.0) / 1000.0,
            "integrity_percent": state.get("structural_integrity"),
            "alarm": state.get("safety_alarm_active"),
            "did": UNISPSC_DID,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("capture", capture_impact_telemetry)
_g.add_node("compute", compute_structural_deformation)
_g.add_node("generate", generate_impact_report)

_g.add_edge(START, "capture")
_g.add_edge("capture", "compute")
_g.add_edge("compute", "generate")
_g.add_edge("generate", END)

graph = _g.compile()
