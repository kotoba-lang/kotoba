from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class SurgicalState(TypedDict):
    product_id: str
    spec_compliance: bool
    sterilization_verified: bool
    logs: List[str]

def validate_medical_grade(state: SurgicalState):
    compliance = state.get("spec_compliance", False)
    return {"logs": state.get("logs", []) + [f"Validation status: {compliance}"]}

def verify_sterility(state: SurgicalState):
    return {"sterilization_verified": True, "logs": state.get("logs", []) + ["Sterility cycle confirmed"]}

builder = StateGraph(SurgicalState)
builder.add_node("validate", validate_medical_grade)
builder.add_node("verify", verify_sterility)
builder.set_entry_point("validate")
builder.add_edge("validate", "verify")
builder.add_edge("verify", END)
graph = builder.compile()
