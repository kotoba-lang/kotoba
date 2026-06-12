from typing import TypedDict
from langgraph.graph import StateGraph, END

class RehabEquipmentState(TypedDict):
    material: str
    spec_compliant: bool
    safety_check: bool

def validate_materials(state: RehabEquipmentState):
    return {"spec_compliant": state.get("material") == "medical_grade_polymer"}

def safety_audit(state: RehabEquipmentState):
    return {"safety_check": True}

graph = StateGraph(RehabEquipmentState)
graph.add_node("validate", validate_materials)
graph.add_node("audit", safety_audit)
graph.set_entry_point("validate")
graph.add_edge("validate", "audit")
graph.add_edge("audit", END)
graph = graph.compile()
