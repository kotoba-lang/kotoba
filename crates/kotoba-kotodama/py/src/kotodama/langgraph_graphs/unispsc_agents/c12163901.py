from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class CatalystState(TypedDict):
    material_id: str
    purity_check: bool
    safety_clearance: bool
    validation_log: Annotated[Sequence[str], operator.add]

def validate_chemical_integrity(state: CatalystState) -> dict:
    # Simulate rigorous validation logic
    return {"purity_check": True, "validation_log": ["Chemical purity verified against batch specs"]}

def perform_safety_review(state: CatalystState) -> dict:
    # Simulate regulatory safety check
    return {"safety_clearance": True, "validation_log": ["Safety clearance passed per industry standards"]}

workflow = StateGraph(CatalystState)
workflow.add_node("validate_integrity", validate_chemical_integrity)
workflow.add_node("safety_review", perform_safety_review)
workflow.set_entry_point("validate_integrity")
workflow.add_edge("validate_integrity", "safety_review")
workflow.add_edge("safety_review", END)

graph = workflow.compile()
