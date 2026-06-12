from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ChemicalProcurementState(TypedDict):
    commodity_code: str
    purity_check_passed: bool
    safety_clearance: bool
    final_status: str

def validate_purity(state: ChemicalProcurementState):
    # Simulate purity verification logic
    return {"purity_check_passed": True}

def perform_safety_review(state: ChemicalProcurementState):
    # Simulate safety and regulatory compliance checks
    return {"safety_clearance": True}

def finalize_procurement(state: ChemicalProcurementState):
    return {"final_status": "APPROVED" if state["purity_check_passed"] and state["safety_clearance"] else "REJECTED"}

graph = StateGraph(ChemicalProcurementState)
graph.add_node("purity_check", validate_purity)
graph.add_node("safety_review", perform_safety_review)
graph.add_node("finalize", finalize_procurement)
graph.set_entry_point("purity_check")
graph.add_edge("purity_check", "safety_review")
graph.add_edge("safety_review", "finalize")
graph.add_edge("finalize", END)
graph = graph.compile()
