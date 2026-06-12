# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21102400 — Irrigation (segment 21).

Bespoke LangGraph implementation for managing irrigation system state,
water resource allocation, and flow optimization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21102400"
UNISPSC_TITLE = "Irrigation"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21102400"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Irrigation
    water_source: str
    target_zone_id: str
    required_volume_liters: float
    system_pressure_ok: bool


def analyze_demand(state: State) -> dict[str, Any]:
    """Analyzes input to determine water requirements and target zones."""
    inp = state.get("input") or {}
    source = inp.get("source", "primary_well")
    zone = inp.get("zone", "sector_a")
    area_sqm = inp.get("area_sqm", 100.0)
    # Estimate 5 liters per square meter
    volume = area_sqm * 5.0

    return {
        "log": [f"{UNISPSC_CODE}:analyze_demand -> zone:{zone}, vol:{volume}"],
        "water_source": source,
        "target_zone_id": zone,
        "required_volume_liters": volume,
    }


def verify_pressure(state: State) -> dict[str, Any]:
    """Simulates system diagnostics for irrigation pressure and pump health."""
    # Logic: Assume pressure is OK if volume is within pump limits (e.g., 2000L)
    volume = state.get("required_volume_liters", 0.0)
    is_ok = 0.0 < volume < 2000.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_pressure -> status:{is_ok}"],
        "system_pressure_ok": is_ok,
    }


def finalize_irrigation_task(state: State) -> dict[str, Any]:
    """Compiles the final irrigation schedule and status report."""
    success = state.get("system_pressure_ok", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_irrigation_task"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "execution_status": "dispatched" if success else "failed_pressure_check",
            "parameters": {
                "source": state.get("water_source"),
                "zone": state.get("target_zone_id"),
                "volume": state.get("required_volume_liters"),
            },
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("analyze_demand", analyze_demand)
_g.add_node("verify_pressure", verify_pressure)
_g.add_node("finalize_irrigation_task", finalize_irrigation_task)

_g.add_edge(START, "analyze_demand")
_g.add_edge("analyze_demand", "verify_pressure")
_g.add_edge("verify_pressure", "finalize_irrigation_task")
_g.add_edge("finalize_irrigation_task", END)

graph = _g.compile()
