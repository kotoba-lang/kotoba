from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    product_id: str
    quality_status: str
    compliance_ok: bool

def validate_composition(state: ProcurementState):
    # Simulate API/Chemical consistency check
    return {"compliance_ok": True}

def check_sterility(state: ProcurementState):
    # Simulate sterility audit process
    return {"quality_status": "Passed"}

graph = StateGraph(ProcurementState)
graph.add_node("validate", validate_composition)
graph.add_node("sterile_check", check_sterility)
graph.set_entry_point("validate")
graph.add_edge("validate", "sterile_check")
graph.add_edge("sterile_check", END)
graph = graph.compile()
