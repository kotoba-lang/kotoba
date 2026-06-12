from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    purity_check: bool
    sanitation_report: str
    approved: bool

def validate_purity(state: ProcurementState) -> dict:
    return {"purity_check": state.get("purity_check", False)}

def verify_safety(state: ProcurementState) -> dict:
    is_safe = state.get("sanitation_report") == "passed"
    return {"approved": is_safe}

graph = StateGraph(ProcurementState)
graph.add_node("validate", validate_purity)
graph.add_node("safety", verify_safety)
graph.add_edge("validate", "safety")
graph.add_edge("safety", END)
graph.set_entry_point("validate")
graph = graph.compile()
