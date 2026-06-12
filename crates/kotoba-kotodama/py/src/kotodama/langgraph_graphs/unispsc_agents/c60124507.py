from typing import TypedDict
from langgraph.graph import StateGraph, END

class SandProcessState(TypedDict):
    purity_check: bool
    safety_certification: bool
    approved: bool

def validate_purity(state: SandProcessState):
    return {"purity_check": True}

def verify_safety(state: SandProcessState):
    return {"safety_certification": True, "approved": True if state.get("purity_check") else False}

graph = StateGraph(SandProcessState)
graph.add_node("purity", validate_purity)
graph.add_node("safety", verify_safety)
graph.add_edge("purity", "safety")
graph.add_edge("safety", END)
graph.set_entry_point("purity")
graph = graph.compile()
