from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END

class CatalystState(TypedDict):
    material_id: str
    purity_check: bool
    safety_clearance: bool
    is_approved: bool

def validate_catalyst_purity(state: CatalystState):
    # Simulate complex CAD/Analytical validation
    return {"purity_check": True}

def check_safety_regulations(state: CatalystState):
    # Simulate dual-use/dangerous-goods check
    return {"safety_clearance": True}

def finalize_approval(state: CatalystState):
    is_approved = state["purity_check"] and state["safety_clearance"]
    return {"is_approved": is_approved}

graph = StateGraph(CatalystState)
graph.add_node("validate", validate_catalyst_purity)
graph.add_node("safety", check_safety_regulations)
graph.add_node("finalize", finalize_approval)
graph.set_entry_point("validate")
graph.add_edge("validate", "safety")
graph.add_edge("safety", "finalize")
graph.add_edge("finalize", END)
graph = graph.compile()
