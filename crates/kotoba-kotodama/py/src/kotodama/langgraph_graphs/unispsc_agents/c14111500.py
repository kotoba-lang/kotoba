from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class PaperProcurementState(TypedDict):
    commodity: str
    spec_compliance: bool
    vendor_risk_score: float
    process_steps: Annotated[Sequence[str], operator.add]

def validate_specs(state: PaperProcurementState):
    # Simulate spec validation logic
    return {"spec_compliance": True, "process_steps": ["Validation of paper GSM and ISO standards"]}

def check_vendor(state: PaperProcurementState):
    # Simulate vendor risk assessment
    return {"vendor_risk_score": 0.1, "process_steps": ["Verified supplier sustainability credentials"]}

builder = StateGraph(PaperProcurementState)
builder.add_node("validate", validate_specs)
builder.add_node("risk_check", check_vendor)
builder.add_edge("validate", "risk_check")
builder.add_edge("risk_check", END)
builder.set_entry_point("validate")
graph = builder.compile()
