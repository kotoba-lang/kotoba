# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25201707"
UNISPSC_TITLE = "Aircraft Gyro"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25201707"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Aircraft Gyro
    drift_rate_deg_h: float
    is_aligned: bool
    flight_hours: int
    health_score: float


def align_gyro(state: State) -> dict[str, Any]:
    """Node: Simulates gyro spin-up and alignment procedure."""
    inp = state.get("input") or {}
    # Simulate drift based on input or defaults
    drift = float(inp.get("drift_rate", 0.02))
    return {
        "log": [f"{UNISPSC_CODE}:align_gyro"],
        "drift_rate_deg_h": drift,
        "is_aligned": drift < 0.1,
    }


def check_reliability(state: State) -> dict[str, Any]:
    """Node: Checks flight hours and drift to determine component health."""
    inp = state.get("input") or {}
    hours = int(inp.get("flight_hours", 250))
    drift = state.get("drift_rate_deg_h", 0.0)

    # Simple health heuristic: starts at 1.0, degrades with hours and drift
    health = max(0.0, 1.0 - (hours / 5000.0) - (drift * 2.0))

    return {
        "log": [f"{UNISPSC_CODE}:check_reliability"],
        "flight_hours": hours,
        "health_score": health,
    }


def generate_telemetry(state: State) -> dict[str, Any]:
    """Node: Formats final aircraft instrumentation telemetry data."""
    health = state.get("health_score", 0.0)
    aligned = state.get("is_aligned", False)

    status_ok = health > 0.7 and aligned

    return {
        "log": [f"{UNISPSC_CODE}:generate_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "telemetry": {
                "drift_rate": state.get("drift_rate_deg_h"),
                "flight_hours": state.get("flight_hours"),
                "health_score": round(health, 3),
                "is_aligned": aligned,
            },
            "status": "GREEN" if status_ok else "YELLOW" if health > 0.4 else "RED",
            "ok": status_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("align", align_gyro)
_g.add_node("reliability", check_reliability)
_g.add_node("telemetry", generate_telemetry)

_g.add_edge(START, "align")
_g.add_edge("align", "reliability")
_g.add_edge("reliability", "telemetry")
_g.add_edge("telemetry", END)

graph = _g.compile()
