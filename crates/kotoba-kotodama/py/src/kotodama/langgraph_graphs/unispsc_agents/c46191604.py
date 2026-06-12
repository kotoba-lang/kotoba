from typing import TypedDict
from langgraph.graph import StateGraph, END

class FireBlanketState(TypedDict):
    specifications: dict
    compliance_ok: bool
    validation_step: str

def validate_materials(state: FireBlanketState):
    # Business logic for material check
    return {"compliance_ok": True, "validation_step": "material_check_complete"}

def check_safety_standards(state: FireBlanketState):
    # Business logic for standard certification verification
    return {"validation_step": "standards_check_complete"}

graph = StateGraph(FireBlanketState)
graph.add_node("validate_materials", validate_materials)
graph.add_node("check_safety_standards", check_safety_standards)
graph.set_entry_point("validate_materials")
graph.add_edge("validate_materials", "check_safety_standards")
graph.add_edge("check_safety_standards", END)
graph = graph.compile()
