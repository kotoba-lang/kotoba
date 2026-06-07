from typing import TypedDict
from langgraph.graph import StateGraph, END

class BabyBathState(TypedDict):
    material_certified: bool
    safety_specs_met: bool
    qc_passed: bool

def check_materials(state: BabyBathState):
    return {"material_certified": True}

def validate_safety(state: BabyBathState):
    return {"safety_specs_met": True}

def final_qc(state: BabyBathState):
    return {"qc_passed": True}

graph = StateGraph(BabyBathState)
graph.add_node("check_mats", check_materials)
graph.add_node("validate_safety", validate_safety)
graph.add_node("qc", final_qc)
graph.set_entry_point("check_mats")
graph.add_edge("check_mats", "validate_safety")
graph.add_edge("validate_safety", "qc")
graph.add_edge("qc", END)
graph = graph.compile()
