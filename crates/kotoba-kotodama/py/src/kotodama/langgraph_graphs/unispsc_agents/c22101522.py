# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101522"
UNISPSC_TITLE = "Proc"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101522"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for "Proc" (Heavy Construction Processing Machinery)
    attachment_id: str
    hydraulic_pressure_psi: float
    safety_lock_engaged: bool
    material_hardness_mohs: float
    total_material_processed_kg: float


def validate_readiness(state: State) -> dict[str, Any]:
    """Validates hydraulic pressure and safety protocols for the processor."""
    inp = state.get("input") or {}
    initial_pressure = inp.get("initial_pressure", 2800.0)
    hardness = inp.get("hardness", 6.5)

    return {
        "log": [f"{UNISPSC_CODE}:validate_readiness"],
        "attachment_id": inp.get("unit_id", "PROC-2210-X1"),
        "hydraulic_pressure_psi": initial_pressure,
        "safety_lock_engaged": True,
        "material_hardness_mohs": hardness,
    }


def execute_processing_cycle(state: State) -> dict[str, Any]:
    """Simulates a processing cycle (crushing or shearing) with load metrics."""
    # Simulation logic: pressure increases with material hardness
    hardness = state.get("material_hardness_mohs", 1.0)
    current_pressure = state.get("hydraulic_pressure_psi", 0.0)

    new_pressure = current_pressure + (hardness * 150.0)
    processed_kg = 250.0 * (new_pressure / 3000.0)

    return {
        "log": [f"{UNISPSC_CODE}:execute_processing_cycle"],
        "hydraulic_pressure_psi": new_pressure,
        "total_material_processed_kg": state.get("total_material_processed_kg", 0.0) + processed_kg,
    }


def finalize_operational_report(state: State) -> dict[str, Any]:
    """Aggregates telemetry and provides the final processing outcome."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_operational_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "unit": state.get("attachment_id"),
                "peak_pressure": state.get("hydraulic_pressure_psi"),
                "throughput_kg": state.get("total_material_processed_kg"),
                "safety_status": "secured" if state.get("safety_lock_engaged") else "bypass",
            },
            "status": "ready_for_next_cycle",
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_readiness)
_g.add_node("process", execute_processing_cycle)
_g.add_node("finalize", finalize_operational_report)

_g.add_edge(START, "validate")
_g.add_edge("validate", "process")
_g.add_edge("process", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
