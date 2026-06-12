from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END

class CatalystState(TypedDict):
    commodity_code: str
    purity_validated: bool
    safety_check_passed: bool
    storage_temp: float

def validate_catalyst_purity(state: CatalystState):
    # Simulate chemical purity verification logic
    return {"purity_validated": True}

def check_safety_protocols(state: CatalystState):
    # Simulate regulatory safety check
    return {"safety_check_passed": True}

graph = StateGraph(CatalystState)
graph.add_node("validate", validate_catalyst_purity)
graph.add_node("safety", check_safety_protocols)
graph.add_edge("validate", "safety")
graph.add_edge("safety", END)
graph.set_entry_point("validate")
graph = graph.compile()
