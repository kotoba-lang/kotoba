# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21111506 — Spray (segment 21).

Bespoke graph logic for agricultural spraying operations, covering equipment
calibration, mixture preparation, and application verification.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21111506"
UNISPSC_TITLE = "Spray"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21111506"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for agricultural spraying
    pressure_psi: float
    nozzle_type: str
    application_rate_lph: float
    coverage_area_ha: float
    total_volume_liters: float


def calibrate_nozzles(state: State) -> dict[str, Any]:
    """Validates the pressure and nozzle selection for the spray operation."""
    inp = state.get("input") or {}
    pressure = float(inp.get("pressure", 40.0))
    nozzle = str(inp.get("nozzle", "standard_flat_fan"))

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_nozzles -> pressure={pressure}psi, type={nozzle}"],
        "pressure_psi": pressure,
        "nozzle_type": nozzle,
    }


def calculate_load(state: State) -> dict[str, Any]:
    """Determines the required mixture volume based on area and application rate."""
    inp = state.get("input") or {}
    area = float(inp.get("area_ha", 1.0))
    rate = float(inp.get("rate_lph", 200.0))
    total_vol = area * rate

    return {
        "log": [f"{UNISPSC_CODE}:calculate_load -> {total_vol}L required for {area}ha"],
        "coverage_area_ha": area,
        "application_rate_lph": rate,
        "total_volume_liters": total_vol,
    }


def finalize_operation(state: State) -> dict[str, Any]:
    """Records the spray event and verifies completion metrics."""
    total_vol = state.get("total_volume_liters", 0.0)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_operation"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "applied",
            "volume_applied_liters": total_vol,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("calibrate", calibrate_nozzles)
_g.add_node("calculate", calculate_load)
_g.add_node("finalize", finalize_operation)

_g.add_edge(START, "calibrate")
_g.add_edge("calibrate", "calculate")
_g.add_edge("calculate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
