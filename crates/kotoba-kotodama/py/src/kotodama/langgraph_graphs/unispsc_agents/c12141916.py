from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ResinState(TypedDict):
    material_id: str
    purity_check: bool
    safety_clearance: bool
    final_spec: dict

def validate_chemistry(state: ResinState):
    # Simulate chemical validation logic
    return {"purity_check": True}

def check_safety_protocols(state: ResinState):
    # Simulate dangerous goods compliance check
    return {"safety_clearance": True}

def finalize_procurement(state: ResinState):
    return {"final_spec": {"status": "APPROVED", "risk_level": "medium"}}

graph = StateGraph(ResinState)
graph.add_node("validate", validate_chemistry)
graph.add_node("safety", check_safety_protocols)
graph.add_node("finalize", finalize_procurement)
graph.add_edge("validate", "safety")
graph.add_edge("safety", "finalize")
graph.add_edge("finalize", END)
graph.set_entry_point("validate")
graph = graph.compile()
