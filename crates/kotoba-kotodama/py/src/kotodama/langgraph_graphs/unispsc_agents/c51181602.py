from typing import TypedDict
from langgraph.graph import StateGraph, END

class PharmState(TypedDict):
    batch_id: str
    compliance_cleared: bool
    expiry_check: bool

def validate_batch(state: PharmState):
    return { "compliance_cleared": True if state.get("batch_id") else False }

def check_stability(state: PharmState):
    return { "expiry_check": True }

graph = StateGraph(PharmState)
graph.add_node("validate", validate_batch)
graph.add_node("stability", check_stability)
graph.set_entry_point("validate")
graph.add_edge("validate", "stability")
graph.add_edge("stability", END)
graph = graph.compile()
