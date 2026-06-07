# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20141801 — Crushing Machinery (segment 20).

Bespoke logic for monitoring and optimizing mining crushing operations, including
vibration analysis, granularity calibration, and throughput management.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20141801"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20141801"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Crushing Machinery
    crusher_id: str
    feed_rate_tph: float
    granularity_mm: float
    vibration_alert: bool
    lube_pressure_psi: float


def monitor_vibration(state: State) -> dict[str, Any]:
    """Analyzes vibration sensors to prevent structural failure of the crusher."""
    inp = state.get("input") or {}
    vibration = inp.get("vibration_level", 0.45)
    return {
        "log": [f"{UNISPSC_CODE}:monitor_vibration"],
        "vibration_alert": vibration > 0.85,
        "crusher_id": inp.get("id", "CR-X1-PRIMARY"),
    }


def calibrate_crush_depth(state: State) -> dict[str, Any]:
    """Adjusts the mantle-concave gap to achieve target output granularity."""
    inp = state.get("input") or {}
    target_mm = inp.get("target_granularity", 12.5)

    # If vibration is high, increase the gap to reduce mechanical stress
    if state.get("vibration_alert"):
        target_mm += 4.0

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_crush_depth"],
        "granularity_mm": target_mm,
        "lube_pressure_psi": 48.2,
    }


def dispatch_load(state: State) -> dict[str, Any]:
    """Calculates final feed rate and emits operational status report."""
    base_rate = 320.0
    is_alert = state.get("vibration_alert", False)

    # Throttle throughput if alerts are active to prevent emergency shutdown
    actual_rate = base_rate * 0.35 if is_alert else base_rate

    return {
        "log": [f"{UNISPSC_CODE}:dispatch_load"],
        "feed_rate_tph": actual_rate,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "operational_data": {
                "crusher_id": state.get("crusher_id"),
                "throughput_tph": actual_rate,
                "output_granularity": state.get("granularity_mm"),
                "system_health": "warning" if is_alert else "optimal",
                "lube_pressure": state.get("lube_pressure_psi")
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("monitor_vibration", monitor_vibration)
_g.add_node("calibrate_crush_depth", calibrate_crush_depth)
_g.add_node("dispatch_load", dispatch_load)

_g.add_edge(START, "monitor_vibration")
_g.add_edge("monitor_vibration", "calibrate_crush_depth")
_g.add_edge("calibrate_crush_depth", "dispatch_load")
_g.add_edge("dispatch_load", END)

graph = _g.compile()
