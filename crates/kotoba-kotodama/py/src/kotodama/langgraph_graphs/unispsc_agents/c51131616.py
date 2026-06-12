from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    purity_check: bool
    temp_log_verified: bool
    compliance_passed: bool

def validate_purity(state: ProcurementState):
    # Simulate chemical assay logic
    return { "purity_check": True }

def check_cold_chain(state: ProcurementState):
    # Simulate IoT temperature threshold check
    return { "temp_log_verified": True }

graph = StateGraph(ProcurementState)
graph.add_node("validate_api", validate_purity)
graph.add_node("verify_cold_chain", check_cold_chain)
graph.set_entry_point("validate_api")
graph.add_edge("validate_api", "verify_cold_chain")
graph.add_edge("verify_cold_chain", END)
graph = graph.compile()
