from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    compliance_docs: list
    temp_log_verified: bool

def validate_gmp(state: ProcurementState):
    return {"compliance_docs": ["GMP_CERT_VALID"]}

def check_cold_chain(state: ProcurementState):
    return {"temp_log_verified": True}

graph = StateGraph(ProcurementState)
graph.add_node("gmp", validate_gmp)
graph.add_node("cold_chain", check_cold_chain)
graph.set_entry_point("gmp")
graph.add_edge("gmp", "cold_chain")
graph.add_edge("cold_chain", END)
graph = graph.compile()
