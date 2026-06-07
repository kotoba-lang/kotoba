from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    quality_verified: bool
    temp_log_valid: bool

def check_quality(state: ProcurementState):
    return {"quality_verified": True}

def validate_cold_chain(state: ProcurementState):
    return {"temp_log_valid": True}

graph = StateGraph(ProcurementState)
graph.add_node("verify_quality", check_quality)
graph.add_node("verify_cold_chain", validate_cold_chain)
graph.set_entry_point("verify_quality")
graph.add_edge("verify_quality", "verify_cold_chain")
graph.add_edge("verify_cold_chain", END)
graph = graph.compile()
