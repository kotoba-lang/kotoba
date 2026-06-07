from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class AlNProcessingState(TypedDict):
    purity_check: bool
    thermal_validation: bool
    certification_docs: list[str]
    status: str

def validate_purity(state: AlNProcessingState):
    # Simulate chemical purity validation logic
    return {"purity_check": True, "status": "Purity Confirmed"}

def validate_thermal_specs(state: AlNProcessingState):
    # Simulate thermal conductivity validation
    return {"thermal_validation": True, "status": "Thermal Specs Validated"}

def finalize_procurement(state: AlNProcessingState):
    return {"status": "Procurement Ready for Approval"}

builder = StateGraph(AlNProcessingState)
builder.add_node("purity", validate_purity)
builder.add_node("thermal", validate_thermal_specs)
builder.add_node("finalizer", finalize_procurement)

builder.set_entry_point("purity")
builder.add_edge("purity", "thermal")
builder.add_edge("thermal", "finalizer")
builder.add_edge("finalizer", END)

graph = builder.compile()
