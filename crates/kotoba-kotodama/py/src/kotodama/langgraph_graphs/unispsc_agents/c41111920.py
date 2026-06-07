from typing import TypedDict
from langgraph.graph import StateGraph, END

class CMMState(TypedDict):
    calibration_data: dict
    precision_check: bool
    approved: bool

def validate_specs(state: CMMState):
    # Simulate validation of ISO 10360 standards
    state["precision_check"] = True
    return state

def approve_procurement(state: CMMState):
    state["approved"] = state["precision_check"]
    return state

graph = StateGraph(CMMState)
graph.add_node("validate", validate_specs)
graph.add_node("approve", approve_procurement)
graph.set_entry_point("validate")
graph.add_edge("validate", "approve")
graph.add_edge("approve", END)
graph = graph.compile()
