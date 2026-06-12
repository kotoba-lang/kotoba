# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26112104.
Segment 26: Power Generation and Distribution Machinery and Accessories.

This bespoke graph manages state transitions for power generation components,
performing specification monitoring, compliance evaluation, and asset reporting.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26112104"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26112104"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific state for Power Generation and Distribution
    nominal_voltage: float
    current_load: float
    is_grid_compliant: bool
    asset_condition: str
    maintenance_cycle_id: str


def monitor_telemetry(state: State) -> dict[str, Any]:
    """Monitors incoming telemetry for voltage and current levels."""
    inp = state.get("input") or {}
    voltage = float(inp.get("voltage", 230.0))
    current = float(inp.get("current", 0.0))
    return {
        "log": [f"{UNISPSC_CODE}:monitor_telemetry"],
        "nominal_voltage": voltage,
        "current_load": current,
        "maintenance_cycle_id": inp.get("cycle_id", "CYC-000"),
    }


def evaluate_compliance(state: State) -> dict[str, Any]:
    """Evaluates the electrical specs against grid compliance standards."""
    v = state.get("nominal_voltage", 0.0)
    # Standard compliance check: 210V - 250V range
    compliant = 210.0 <= v <= 250.0
    condition = "OPTIMAL" if compliant else "DEGRADED"

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_compliance"],
        "is_grid_compliant": compliant,
        "asset_condition": condition,
    }


def emit_asset_status(state: State) -> dict[str, Any]:
    """Finalizes the asset registration and emits the compliance report."""
    compliant = state.get("is_grid_compliant", False)
    return {
        "log": [f"{UNISPSC_CODE}:emit_asset_status"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": state.get("asset_condition"),
            "compliance": {
                "verified": compliant,
                "voltage": state.get("nominal_voltage"),
                "load": state.get("current_load"),
            },
            "cycle": state.get("maintenance_cycle_id"),
            "ok": compliant,
        },
    }


_g = StateGraph(State)
_g.add_node("monitor", monitor_telemetry)
_g.add_node("evaluate", evaluate_compliance)
_g.add_node("emit", emit_asset_status)

_g.add_edge(START, "monitor")
_g.add_edge("monitor", "evaluate")
_g.add_edge("evaluate", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
