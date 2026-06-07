from typing import TypedDict
from langgraph.graph import StateGraph, END

class DeicerState(TypedDict):
    msds_path: str
    freezing_point: float
    pass_compliance: bool

def validate_msds(state: DeicerState):
    # Simulate MSDS compliance check
    return {"pass_compliance": state.get("freezing_point", 0) < 0}

def route_compliance(state: DeicerState):
    return "compliant" if state["pass_compliance"] else "rejected"

graph = StateGraph(DeicerState)
graph.add_node("validate", validate_msds)
graph.add_conditional_edges("validate", route_compliance, {"compliant": END, "rejected": END})
graph.set_entry_point("validate")
graph = graph.compile()
