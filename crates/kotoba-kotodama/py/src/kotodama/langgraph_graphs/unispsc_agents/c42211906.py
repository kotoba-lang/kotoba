from langgraph.graph import StateGraph, END
from typing import TypedDict

class ProcurementState(TypedDict):
    spec_compliance: bool
    safety_check: bool
    order_id: str

def validate_specs(state: ProcurementState):
    state["spec_compliance"] = True
    return state

def check_safety_standards(state: ProcurementState):
    state["safety_check"] = True
    return state

graph = StateGraph(ProcurementState)
graph.add_node("validate_specs", validate_specs)
graph.add_node("safety_check", check_safety_standards)
graph.add_edge("validate_specs", "safety_check")
graph.add_edge("safety_check", END)
graph.set_entry_point("validate_specs")
graph = graph.compile()
