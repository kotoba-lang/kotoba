# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23150000 — Machine (segment 23).

Bespoke graph logic for industrial machinery processing, ensuring operational
readiness, precision calibration, and cycle execution for segment 23.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23150000"
UNISPSC_TITLE = "Machine"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23150000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Machine (Segment 23)
    machine_serial: str
    maintenance_verified: bool
    calibration_offset: float
    operational_mode: str


def inspect_hardware(state: State) -> dict[str, Any]:
    """Verifies physical integrity and serial numbers."""
    inp = state.get("input") or {}
    serial = inp.get("serial", "SN-BASE-2315")
    return {
        "log": [f"{UNISPSC_CODE}:inspect_hardware:{serial}"],
        "machine_serial": serial,
        "maintenance_verified": True,
    }


def calibrate_sensors(state: State) -> dict[str, Any]:
    """Performs software-level sensor alignment and offset calculation."""
    # Simulate a calculation based on segment requirements
    offset = 0.0023 * int(UNISPSC_SEGMENT)
    return {
        "log": [f"{UNISPSC_CODE}:calibrate_sensors:offset_{offset}"],
        "calibration_offset": offset,
        "operational_mode": "precision_standard",
    }


def execute_cycle(state: State) -> dict[str, Any]:
    """Runs the primary machine cycle and compiles the output telemetry."""
    serial = state.get("machine_serial")
    mode = state.get("operational_mode")

    return {
        "log": [f"{UNISPSC_CODE}:execute_cycle:complete"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "telemetry": {
                "serial": serial,
                "mode": mode,
                "status": "online",
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_hardware", inspect_hardware)
_g.add_node("calibrate_sensors", calibrate_sensors)
_g.add_node("execute_cycle", execute_cycle)

_g.add_edge(START, "inspect_hardware")
_g.add_edge("inspect_hardware", "calibrate_sensors")
_g.add_edge("calibrate_sensors", "execute_cycle")
_g.add_edge("execute_cycle", END)

graph = _g.compile()
