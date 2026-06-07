from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class MathAidState(TypedDict):
    material_compliance: bool
    safety_certs: List[str]
    spec_is_valid: bool

def validate_materials(state: MathAidState):
    return {"material_compliance": True}

def check_safety_standards(state: MathAidState):
    required = ["ASTM F963", "EN71"]
    valid = all(cert in state.get("safety_certs", []) for cert in required)
    return {"spec_is_valid": valid}

graph = StateGraph(MathAidState)
graph.add_node("material_check", validate_materials)
graph.add_node("safety_check", check_safety_standards)
graph.set_entry_point("material_check")
graph.add_edge("material_check", "safety_check")
graph.add_edge("safety_check", END)
graph = graph.compile()
