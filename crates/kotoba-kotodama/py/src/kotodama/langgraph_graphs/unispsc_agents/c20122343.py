from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class RobotProcurementState(TypedDict):
    part_id: str
    safety_specs: dict
    validation_passed: bool
    log: List[str]

def validate_safety_compliance(state: RobotProcurementState):
    specs = state.get("safety_specs", {})
    passed = specs.get("iso10218", False)
    return {"validation_passed": passed, "log": ["Safety check: " + ("Passed" if passed else "Failed")]}

def prepare_logistics(state: RobotProcurementState):
    if state["validation_passed"]:
        return {"log": ["Preparing industrial shipping compliance."]}
    return {"log": ["Flagged for secondary safety review."]}

graph = StateGraph(RobotProcurementState)
graph.add_node("safety", validate_safety_compliance)
graph.add_node("logistics", prepare_logistics)
graph.set_entry_point("safety")
graph.add_edge("safety", "logistics")
graph.add_edge("logistics", END)
graph = graph.compile()
