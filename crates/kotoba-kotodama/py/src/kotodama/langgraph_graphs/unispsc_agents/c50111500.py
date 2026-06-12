from typing import TypedDict
from langgraph.graph import StateGraph, END

class MeatProcurementState(TypedDict):
    order_id: str
    temp_log_verified: bool
    is_safe: bool

def validate_temp(state: MeatProcurementState):
    # Simulate temperature validation logic for cold chain
    return {"temp_log_verified": True}

def safety_check(state: MeatProcurementState):
    # Simulate chemical/bacteria safety analysis check
    return {"is_safe": True}

graph = StateGraph(MeatProcurementState)
graph.add_node("temp_check", validate_temp)
graph.add_node("safety_check", safety_check)
graph.set_entry_point("temp_check")
graph.add_edge("temp_check", "safety_check")
graph.add_edge("safety_check", END)
graph = graph.compile()
