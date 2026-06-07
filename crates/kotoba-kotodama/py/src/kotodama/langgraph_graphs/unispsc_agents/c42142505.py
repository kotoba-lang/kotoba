from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    product_id: str
    compliance_passed: bool
    sterilization_verified: bool

def validate_medical_compliance(state: ProcurementState) -> dict:
    # Logic to verify ISO 13485 and regulatory markers
    return {"compliance_passed": True}

def check_sterilization_certs(state: ProcurementState) -> dict:
    # Verify ETO/Gamma sterilization records
    return {"sterilization_verified": True}

graph = StateGraph(ProcurementState)
graph.add_node("validate", validate_medical_compliance)
graph.add_node("check_certs", check_sterilization_certs)
graph.add_edge("validate", "check_certs")
graph.add_edge("check_certs", END)
graph.set_entry_point("validate")
graph = graph.compile()
