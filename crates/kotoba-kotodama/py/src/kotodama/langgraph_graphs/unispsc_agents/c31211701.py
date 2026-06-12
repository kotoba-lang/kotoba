from typing import TypedDict
from langgraph.graph import StateGraph, END

class GlazeState(TypedDict):
    composition: str
    safety_check: bool
    compliance_report: str

def validate_msds(state: GlazeState):
    # Business logic for MSDS compliance verification
    return {"safety_check": True}

def generate_spec(state: GlazeState):
    # Logic to aggregate technical specs and certificates
    return {"compliance_report": "Verified for industrial use"}

builder = StateGraph(GlazeState)
builder.add_node("validate", validate_msds)
builder.add_node("spec_gen", generate_spec)
builder.add_edge("validate", "spec_gen")
builder.add_edge("spec_gen", END)
builder.set_entry_point("validate")
graph = builder.compile()
