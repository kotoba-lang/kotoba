# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12162300"
UNISPSC_TITLE = "Chem Process"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12162300"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific state for chemical processing
    batch_identifier: str
    target_temperature_k: float
    vessel_pressure_bar: float
    catalyst_load_kg: float
    safety_seal_intact: bool


def configure_reactor(state: State) -> dict[str, Any]:
    """Initializes the reactor state and validates safety protocols."""
    inp = state.get("input") or {}
    batch_id = inp.get("batch", "CP-BATCH-001")
    return {
        "log": [f"{UNISPSC_CODE}:configure_reactor"],
        "batch_identifier": batch_id,
        "target_temperature_k": 373.15,
        "safety_seal_intact": True,
    }


def execute_thermal_cycle(state: State) -> dict[str, Any]:
    """Simulates the chemical reaction cycle by adjusting heat and pressure."""
    # Logic simulating a stable process ramp
    current_temp = state.get("target_temperature_k", 298.15)
    pressure = (current_temp / 100.0) * 1.5
    return {
        "log": [f"{UNISPSC_CODE}:execute_thermal_cycle"],
        "vessel_pressure_bar": pressure,
        "catalyst_load_kg": 5.25,
    }


def analyze_purity(state: State) -> dict[str, Any]:
    """Final assessment of the chemical output purity and yield."""
    pressure = state.get("vessel_pressure_bar", 0.0)
    is_valid = 4.0 < pressure < 7.0 and state.get("safety_seal_intact", False)

    return {
        "log": [f"{UNISPSC_CODE}:analyze_purity"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "batch": state.get("batch_identifier"),
            "diagnostics": {
                "pressure_at_finish": pressure,
                "safety_check": state.get("safety_seal_intact"),
            },
            "purity_grade": "A" if is_valid else "Rejected",
            "ok": is_valid,
        },
    }


_g = StateGraph(State)
_g.add_node("configure_reactor", configure_reactor)
_g.add_node("execute_thermal_cycle", execute_thermal_cycle)
_g.add_node("analyze_purity", analyze_purity)

_g.add_edge(START, "configure_reactor")
_g.add_edge("configure_reactor", "execute_thermal_cycle")
_g.add_edge("execute_thermal_cycle", "analyze_purity")
_g.add_edge("analyze_purity", END)

graph = _g.compile()
