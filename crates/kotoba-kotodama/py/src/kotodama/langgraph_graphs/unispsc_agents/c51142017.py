from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    quality_check_passed: bool
    gmp_status: str

def validate_coa(state: ProcurementState):
    return {"quality_check_passed": True}

def check_gmp(state: ProcurementState):
    return {"gmp_status": "Verified"}

graph = StateGraph(ProcurementState)
graph.add_node("validate_coa", validate_coa)
graph.add_node("check_gmp", check_gmp)
graph.add_edge("validate_coa", "check_gmp")
graph.add_edge("check_gmp", END)
graph.set_entry_point("validate_coa")
graph = graph.compile()
