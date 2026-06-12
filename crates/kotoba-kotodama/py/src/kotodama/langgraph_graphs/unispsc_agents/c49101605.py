from typing import TypedDict
from langgraph.graph import StateGraph, END

class AntiqueRugState(TypedDict):
    rug_id: str
    provenance_verified: bool
    condition_score: float
    final_approval: bool

def verify_provenance(state: AntiqueRugState):
    # Simulate authentication logic
    return {"provenance_verified": True}

def assess_condition(state: AntiqueRugState):
    # Validate condition report existence
    return {"condition_score": 9.5}

def finalize_order(state: AntiqueRugState):
    return {"final_approval": True}

graph = StateGraph(AntiqueRugState)
graph.add_node("verify", verify_provenance)
graph.add_node("assess", assess_condition)
graph.add_node("finalize", finalize_order)
graph.set_entry_point("verify")
graph.add_edge("verify", "assess")
graph.add_edge("assess", "finalize")
graph.add_edge("finalize", END)
graph = graph.compile()
