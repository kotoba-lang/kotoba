from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    product_id: str
    cold_chain_status: bool
    gmp_verified: bool

def validate_cold_chain(state: ProcurementState):
    return {"cold_chain_status": True if state.get("temperature_log") else False}

def verify_med_cert(state: ProcurementState):
    return {"gmp_verified": True}

graph = StateGraph(ProcurementState)
graph.add_node("cold_chain", validate_cold_chain)
graph.add_node("gmp_check", verify_med_cert)
graph.set_entry_point("cold_chain")
graph.add_edge("cold_chain", "gmp_check")
graph.add_edge("gmp_check", END)
graph = graph.compile()
