from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    product_code: str
    compliance_cleared: bool
    temp_validated: bool

def validate_gmp(state: ProcurementState):
    return {"compliance_cleared": True}

def check_cold_chain(state: ProcurementState):
    return {"temp_validated": True}

graph = StateGraph(ProcurementState)
graph.add_node("gmp_check", validate_gmp)
graph.add_node("cold_chain_check", check_cold_chain)
graph.add_edge("gmp_check", "cold_chain_check")
graph.add_edge("cold_chain_check", END)
graph.set_entry_point("gmp_check")
graph = graph.compile()
