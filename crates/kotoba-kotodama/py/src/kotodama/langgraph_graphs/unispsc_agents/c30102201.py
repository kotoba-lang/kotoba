from typing import TypedDict
from langgraph.graph import StateGraph, END

class AlloyState(TypedDict):
    material_grade: str
    quality_report: str
    status: str

def validate_chemistry(state: AlloyState):
    # Simulate chemistry compliance check
    return {"status": "validated" if state.get("quality_report") else "pending"}

def approve_order(state: AlloyState):
    return {"status": "approved"}

builder = StateGraph(AlloyState)
builder.add_node("validate", validate_chemistry)
builder.add_node("approve", approve_order)
builder.set_entry_point("validate")
builder.add_edge("validate", "approve")
builder.add_edge("approve", END)
graph = builder.compile()
