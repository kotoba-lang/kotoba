from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class QuartzState(TypedDict):
    purity_check: bool
    thermal_validation: bool
    approved: bool

def validate_purity(state: QuartzState):
    return {"purity_check": True}

def validate_thermal(state: QuartzState):
    return {"thermal_validation": True}

def finalize_approval(state: QuartzState):
    return {"approved": state["purity_check"] and state["thermal_validation"]}

graph = StateGraph(QuartzState)
graph.add_node("purity", validate_purity)
graph.add_node("thermal", validate_thermal)
graph.add_node("approval", finalize_approval)
graph.add_edge("purity", "thermal")
graph.add_edge("thermal", "approval")
graph.add_edge("approval", END)
graph.set_entry_point("purity")
graph = graph.compile()
