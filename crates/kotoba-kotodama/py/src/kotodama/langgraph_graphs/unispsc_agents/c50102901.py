from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    temp_log_verified: bool
    quality_passed: bool
    vendor_approved: bool

def check_cold_chain(state: ProcurementState):
    return {"temp_log_verified": True}

def validate_quality(state: ProcurementState):
    return {"quality_passed": True}

graph = StateGraph(ProcurementState)
graph.add_node("cold_chain", check_cold_chain)
graph.add_node("quality", validate_quality)
graph.set_entry_point("cold_chain")
graph.add_edge("cold_chain", "quality")
graph.add_edge("quality", END)
graph = graph.compile()
