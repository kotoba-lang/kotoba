from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    temp_log_verified: bool
    is_compliant: bool

def check_cold_chain(state: ProcurementState):
    return {"temp_log_verified": True}

def validate_gmp(state: ProcurementState):
    return {"is_compliant": True}

graph = StateGraph(ProcurementState)
graph.add_node("cold_chain", check_cold_chain)
graph.add_node("gmp_check", validate_gmp)
graph.set_entry_point("cold_chain")
graph.add_edge("cold_chain", "gmp_check")
graph.add_edge("gmp_check", END)
graph = graph.compile()
