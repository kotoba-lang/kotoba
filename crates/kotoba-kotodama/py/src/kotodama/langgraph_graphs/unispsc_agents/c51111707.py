from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    drug_name: str
    compliance_cleared: bool
    temp_log_verified: bool

def validate_chemistry(state: ProcurementState):
    return {"compliance_cleared": True}

def check_cold_chain(state: ProcurementState):
    return {"temp_log_verified": True}

graph = StateGraph(ProcurementState)
graph.add_node("chem_validation", validate_chemistry)
graph.add_node("cold_chain_audit", check_cold_chain)
graph.set_entry_point("chem_validation")
graph.add_edge("chem_validation", "cold_chain_audit")
graph.add_edge("cold_chain_audit", END)
graph = graph.compile()
