from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    compliance_validated: bool
    temp_log_verified: bool

def validate_cold_chain(state: ProcurementState):
    return {"temp_log_verified": True}

def check_compliance(state: ProcurementState):
    return {"compliance_validated": True}

graph = StateGraph(ProcurementState)
graph.add_node("validate_compliance", check_compliance)
graph.add_node("verify_cold_chain", validate_cold_chain)
graph.set_entry_point("validate_compliance")
graph.add_edge("validate_compliance", "verify_cold_chain")
graph.add_edge("verify_cold_chain", END)
graph = graph.compile()
