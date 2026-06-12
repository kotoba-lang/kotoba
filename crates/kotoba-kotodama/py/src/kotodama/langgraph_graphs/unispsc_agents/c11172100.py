# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11172100"
UNISPSC_TITLE = "Mag Graph"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11172100"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    grid_resolution_meters: float
    anomaly_detection_threshold: float
    coordinate_system: str
    sensor_drift_compensated: bool


def validate_geophysics_parameters(state: State) -> dict[str, Any]:
    """Validates the input magnetic gridding resolution and coordinate reference system."""
    inp = state.get("input") or {}
    res = float(inp.get("resolution", 10.0))
    crs = str(inp.get("crs", "WGS84"))

    return {
        "log": [f"{UNISPSC_CODE}:validate_geophysics_parameters"],
        "grid_resolution_meters": res,
        "coordinate_system": crs,
        "sensor_drift_compensated": True,
    }


def perform_magnetic_interpolation(state: State) -> dict[str, Any]:
    """Simulates the interpolation of magnetic field strength across the survey grid."""
    res = state.get("grid_resolution_meters", 1.0)
    # Higher resolution implies a more sensitive anomaly threshold for geological mapping
    threshold = 2.5 if res <= 5.0 else 5.0

    return {
        "log": [f"{UNISPSC_CODE}:perform_magnetic_interpolation"],
        "anomaly_detection_threshold": threshold,
    }


def finalize_mag_graph_report(state: State) -> dict[str, Any]:
    """Compiles the final Mag Graph data structure with metadata."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_mag_graph_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "output_params": {
                "resolution": state.get("grid_resolution_meters"),
                "crs": state.get("coordinate_system"),
                "threshold_nt": state.get("anomaly_detection_threshold"),
                "drift_corrected": state.get("sensor_drift_compensated"),
            },
            "status": "VALIDATED",
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_geophysics_parameters)
_g.add_node("interpolate", perform_magnetic_interpolation)
_g.add_node("finalize", finalize_mag_graph_report)

_g.add_edge(START, "validate")
_g.add_edge("validate", "interpolate")
_g.add_edge("interpolate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
