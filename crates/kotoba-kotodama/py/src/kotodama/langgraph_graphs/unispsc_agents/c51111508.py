from typing import TypedDict
from langgraph.graph import StateGraph, END

class DrugProcurementState(TypedDict):
    drug_name: str
    compliance_checked: bool
    temp_log_verified: bool

def validate_compliance(state: DrugProcurementState):
    return {"compliance_checked": True}

def verify_cold_chain(state: DrugProcurementState):
    return {"temp_log_verified": True}

builder = StateGraph(DrugProcurementState)
builder.add_node("validate", validate_compliance)
builder.add_node("verify_temp", verify_cold_chain)
builder.set_entry_point("validate")
builder.add_edge("validate", "verify_temp")
builder.add_edge("verify_temp", END)
graph = builder.compile()
