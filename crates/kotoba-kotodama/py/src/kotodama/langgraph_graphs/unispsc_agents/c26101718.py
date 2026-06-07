# codemod:2605231400-unispsc-gemini-bespoke v1
import operator
from typing import Annotated, Any, TypedDict
from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101718"
UNISPSC_TITLE = "Ignition"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101718"

class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    safety_interlock_engaged: bool
    fuel_flow_confirmed: bool
    spark_voltage_kv: float
    sequence_stage: str

def check_interlocks(state: State) -> dict[str, Any]:
    """Validates that all safety interlocks are engaged before proceeding."""
    inp = state.get("input") or {}
    # Simulate hardware interlock check from input or default to True
    engaged = inp.get("interlock", True)
    return {
        "log": [f"{UNISPSC_CODE}:check_interlocks - state: {engaged}"],
        "safety_interlock_engaged": engaged,
        "sequence_stage": "pre-ignition"
    }

def initiate_discharge(state: State) -> dict[str, Any]:
    """Activates the high-voltage ignition discharge if safety permits."""
    if not state.get("safety_interlock_engaged"):
        return {
            "log": [f"{UNISPSC_CODE}:initiate_discharge - safety fault, aborting"],
            "sequence_stage": "fault"
        }

    # Simulate ignition spark discharge
    voltage = 14.5
    return {
        "log": [f"{UNISPSC_CODE}:initiate_discharge - spark active at {voltage}kV"],
        "spark_voltage_kv": voltage,
        "fuel_flow_confirmed": True,
        "sequence_stage": "discharging"
    }

def monitor_combustion(state: State) -> dict[str, Any]:
    """Verifies successful ignition and transition to stable combustion."""
    success = state.get("fuel_flow_confirmed", False) and state.get("spark_voltage_kv", 0) > 10.0
    status = "stable" if success else "failed"

    return {
        "log": [f"{UNISPSC_CODE}:monitor_combustion - status: {status}"],
        "sequence_stage": status,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "ignited" if success else "ignition_failure",
            "ok": success,
        },
    }

_g = StateGraph(State)
_g.add_node("check_interlocks", check_interlocks)
_g.add_node("initiate_discharge", initiate_discharge)
_g.add_node("monitor_combustion", monitor_combustion)

_g.add_edge(START, "check_interlocks")
_g.add_edge("check_interlocks", "initiate_discharge")
_g.add_edge("initiate_discharge", "monitor_combustion")
_g.add_edge("monitor_combustion", END)

graph = _g.compile()
