from typing import TypedDict
from langgraph.graph import StateGraph, END

class MandarinState(TypedDict):
    quality_score: float
    temp_check: bool
    approved: bool

def check_freshness(state: MandarinState):
    return {"temp_check": state.get("quality_score", 0) > 8.0}

def approve_shipment(state: MandarinState):
    return {"approved": state.get("temp_check", False)}

graph = StateGraph(MandarinState)
graph.add_node("check", check_freshness)
graph.add_node("approve", approve_shipment)
graph.set_entry_point("check")
graph.add_edge("check", "approve")
graph.add_edge("approve", END)
graph = graph.compile()
