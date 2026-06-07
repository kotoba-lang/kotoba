from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
import operator

class BrakeProcurementState(TypedDict):
    part_number: str
    safety_specs: dict
    inspection_status: str
    compliance_log: Annotated[Sequence[str], operator.add]

def validate_safety_standards(state: BrakeProcurementState) -> BrakeProcurementState:
    # Simulate CAD/Spec validation for critical safety parts
    if "iso_16032" in state.get("safety_specs", {}):
        state["inspection_status"] = "PASSED"
        state["compliance_log"] = ["Validated ISO-16032 safety standards"]
    else:
        state["inspection_status"] = "FAILED"
        state["compliance_log"] = ["Missing critical safety certification"]
    return state

def assembly_readiness(state: BrakeProcurementState) -> BrakeProcurementState:
    if state["inspection_status"] == "PASSED":
        state["compliance_log"].append("Approved for procurement workflow")
    return state

graph = StateGraph(BrakeProcurementState)
graph.add_node("validate", validate_safety_standards)
graph.add_node("readiness", assembly_readiness)
graph.add_edge("validate", "readiness")
graph.add_edge("readiness", END)
graph.set_entry_point("validate")
graph = graph.compile()
