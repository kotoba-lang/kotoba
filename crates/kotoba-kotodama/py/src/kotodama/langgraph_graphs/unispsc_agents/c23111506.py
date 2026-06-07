# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23111506"
UNISPSC_TITLE = "Pump"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23111506"


class State(TypedDict, total=False):
    # Core fields
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]

    # Domain state for Pump
    pump_type: str
    flow_rate_gpm: float
    head_pressure_psi: float
    efficiency_rating: float
    operational_status: str


def initialize_pump(state: State) -> dict[str, Any]:
    """Parses input configuration and initializes pump baseline parameters."""
    inp = state.get("input") or {}
    p_type = str(inp.get("pump_type", "Centrifugal"))
    flow = float(inp.get("flow_rate", 100.0))

    return {
        "log": [f"{UNISPSC_CODE}:initialize_pump"],
        "pump_type": p_type,
        "flow_rate_gpm": flow,
        "operational_status": "starting",
    }


def analyze_performance(state: State) -> dict[str, Any]:
    """Simulates hydraulic performance and efficiency metrics."""
    flow = state.get("flow_rate_gpm", 0.0)

    # Model: Pressure decreases as flow increases for standard pumps
    pressure = max(0.0, 60.0 - (flow * 0.3))

    # Efficiency peak modeled as a curve centered around 100 GPM
    efficiency = max(0.0, 0.85 - abs(100.0 - flow) * 0.005)

    status = "optimal" if efficiency > 0.75 else "sub-optimal"
    if pressure < 5.0 and flow > 0:
        status = "cavitation_risk"
    elif flow == 0:
        status = "idling"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_performance"],
        "head_pressure_psi": round(pressure, 2),
        "efficiency_rating": round(efficiency, 3),
        "operational_status": status,
    }


def generate_manifest(state: State) -> dict[str, Any]:
    """Compiles the final state into a standardized result manifest."""
    return {
        "log": [f"{UNISPSC_CODE}:generate_manifest"],
        "result": {
            "asset": UNISPSC_TITLE,
            "code": UNISPSC_CODE,
            "did": UNISPSC_DID,
            "telemetry": {
                "gpm": state.get("flow_rate_gpm"),
                "psi": state.get("head_pressure_psi"),
                "efficiency": state.get("efficiency_rating"),
            },
            "status": state.get("operational_status"),
            "compliance": {
                "ready": state.get("operational_status") not in ["cavitation_risk", "starting"],
                "segment": UNISPSC_SEGMENT,
            },
        },
    }


_g = StateGraph(State)

_g.add_node("initialize", initialize_pump)
_g.add_node("analyze", analyze_performance)
_g.add_node("manifest", generate_manifest)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "analyze")
_g.add_edge("analyze", "manifest")
_g.add_edge("manifest", END)

graph = _g.compile()
