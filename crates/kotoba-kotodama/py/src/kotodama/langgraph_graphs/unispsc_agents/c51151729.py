from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_id: str
    license_validated: bool
    compliance_cleared: bool

def validate_compliance(state: ProcurementState):
    # Implement logic to check narcotics handling clearance
    print("Validating strict compliance for controlled substance...")
    return {"compliance_cleared": True}

def authenticate_user(state: ProcurementState):
    print("Verifying narcotics license...")
    return {"license_validated": True}

workflow = StateGraph(ProcurementState)
workflow.add_node("auth", authenticate_user)
workflow.add_node("validate", validate_compliance)
workflow.set_entry_point("auth")
workflow.add_edge("auth", "validate")
workflow.add_edge("validate", END)
graph = workflow.compile()
