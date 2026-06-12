# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21101808 — Frost protection equipment (segment 21).

Bespoke logic for monitoring ambient temperatures, assessing frost risk,
and managing the deployment of frost protection equipment such as heaters,
wind machines, or irrigation systems used for crop thermal protection.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21101808"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21101808"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Frost protection equipment
    ambient_temperature_c: float
    activation_threshold_c: float
    protection_active: bool
    fuel_reserve_percent: float
    system_health_status: str


def monitor_environmental_data(state: State) -> dict[str, Any]:
    """Monitor sensor inputs for ambient temperature and system status."""
    inp = state.get("input") or {}

    # Extract telemetry or use defaults
    current_temp = float(inp.get("temperature", 4.5))
    threshold = float(inp.get("threshold", 2.0))
    fuel = float(inp.get("fuel", 85.0))

    return {
        "log": [f"{UNISPSC_CODE}:monitor_environmental_data"],
        "ambient_temperature_c": current_temp,
        "activation_threshold_c": threshold,
        "fuel_reserve_percent": fuel,
    }


def assess_frost_risk(state: State) -> dict[str, Any]:
    """Assess the risk of frost damage and decide on equipment activation."""
    temp = state.get("ambient_temperature_c", 0.0)
    threshold = state.get("activation_threshold_c", 0.0)
    fuel = state.get("fuel_reserve_percent", 0.0)

    # Activate if temperature drops below threshold and fuel is available
    should_activate = (temp <= threshold) and (fuel > 5.0)
    health = "operational" if fuel > 10.0 else "low_fuel_warning"

    return {
        "log": [f"{UNISPSC_CODE}:assess_frost_risk"],
        "protection_active": should_activate,
        "system_health_status": health,
    }


def generate_deployment_report(state: State) -> dict[str, Any]:
    """Generate a final report on system deployment and environmental status."""
    is_active = state.get("protection_active", False)
    temp = state.get("ambient_temperature_c", 0.0)
    health = state.get("system_health_status", "unknown")

    return {
        "log": [f"{UNISPSC_CODE}:generate_deployment_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "deployment_status": {
                "active": is_active,
                "ambient_temp": f"{temp}°C",
                "health": health,
                "action": "HEATING_ACTIVE" if is_active else "MONITORING_ONLY"
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("monitor", monitor_environmental_data)
_g.add_node("assess", assess_frost_risk)
_g.add_node("report", generate_deployment_report)

_g.add_edge(START, "monitor")
_g.add_edge("monitor", "assess")
_g.add_edge("assess", "report")
_g.add_edge("report", END)

graph = _g.compile()
