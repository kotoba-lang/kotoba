from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    product_id: str
    compliance_passed: bool
    inspection_result: str

def validate_medical_grade(state: ProcurementState):
    # Simulate biocompatibility and ISO 13485 check
    return {"compliance_passed": True}

def perform_quality_inspection(state: ProcurementState):
    return {"inspection_result": "Pass - Sterile Packaging"}

graph = StateGraph(ProcurementState)
graph.add_node("validate", validate_medical_grade)
graph.add_node("inspect", perform_quality_inspection)
graph.add_edge("validate", "inspect")
graph.add_edge("inspect", END)
graph.set_entry_point("validate")

graph = graph.compile()
