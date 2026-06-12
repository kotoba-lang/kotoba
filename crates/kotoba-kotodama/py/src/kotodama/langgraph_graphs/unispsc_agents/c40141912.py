from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class DuctState(TypedDict):
    specifications: dict
    validation_status: bool
    compliance_report: str

def validate_duct_specs(state: DuctState):
    specs = state.get("specifications", {})
    # Check for mandatory material and pressure specs
    valid = "material" in specs and "pressure_rating" in specs
    return {"validation_status": valid, "compliance_report": "Validated" if valid else "Failed"}

builder = StateGraph(DuctState)
builder.add_node("validate", validate_duct_specs)
builder.set_entry_point("validate")
builder.add_edge("validate", END)
graph = builder.compile()
