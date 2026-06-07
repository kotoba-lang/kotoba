from typing import TypedDict
from langgraph.graph import StateGraph, END

class WheelProcurementState(TypedDict):
    part_number: str
    spec_compliant: bool
    inspection_result: str

def validate_specs(state: WheelProcurementState):
    # Simulate CAD and load requirement validation
    compliant = "load_rating" in state and "material" in state
    return {"spec_compliant": compliant}

def perform_qa(state: WheelProcurementState):
    return {"inspection_result": "passed" if state["spec_compliant"] else "failed"}

graph = StateGraph(WheelProcurementState)
graph.add_node("validate", validate_specs)
graph.add_node("qa", perform_qa)
graph.set_entry_point("validate")
graph.add_edge("validate", "qa")
graph.add_edge("qa", END)
graph = graph.compile()
