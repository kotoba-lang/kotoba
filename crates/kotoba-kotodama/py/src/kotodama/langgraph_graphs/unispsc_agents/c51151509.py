from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    quality_status: str
    compliance_cleared: bool

def validate_gmp(state: ProcurementState):
    return {"compliance_cleared": True}

def check_storage(state: ProcurementState):
    return {"quality_status": "Validated"}

graph = StateGraph(ProcurementState)
graph.add_node("validate_gmp", validate_gmp)
graph.add_node("check_storage", check_storage)
graph.set_entry_point("validate_gmp")
graph.add_edge("validate_gmp", "check_storage")
graph.add_edge("check_storage", END)
graph = graph.compile()
