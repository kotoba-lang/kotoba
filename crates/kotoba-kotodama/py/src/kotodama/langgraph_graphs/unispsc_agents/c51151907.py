from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    product_name: str
    gmp_certified: bool
    purity_level: float
    status: str

def validate_pharmaceutical(state: ProcurementState):
    if not state.get('gmp_certified'):
        return {"status": "FAILED_GMP_REQUIREMENT"}
    if state.get('purity_level', 0) < 99.0:
        return {"status": "FAILED_PURITY_STANDARD"}
    return {"status": "COMPLIANT"}

builder = StateGraph(ProcurementState)
builder.add_node("validate", validate_pharmaceutical)
builder.set_entry_point("validate")
builder.add_edge("validate", END)
graph = builder.compile()
