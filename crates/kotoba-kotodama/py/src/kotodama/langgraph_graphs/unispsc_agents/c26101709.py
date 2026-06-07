from typing import TypedDict
from langgraph.graph import StateGraph, END

class CamshaftState(TypedDict):
    part_number: str
    material_certified: bool
    tolerance_check_passed: bool
    is_approved: bool

def validate_materials(state: CamshaftState):
    # Simulate material compliance check
    return {"material_certified": True}

def validate_tolerances(state: CamshaftState):
    # Simulate dimensional inspection logic
    return {"tolerance_check_passed": True}

def finalize_approval(state: CamshaftState):
    approved = state["material_certified"] and state["tolerance_check_passed"]
    return {"is_approved": approved}

graph = StateGraph(CamshaftState)
graph.add_node("material_check", validate_materials)
graph.add_node("tolerance_check", validate_tolerances)
graph.add_node("final", finalize_approval)
graph.set_entry_point("material_check")
graph.add_edge("material_check", "tolerance_check")
graph.add_edge("tolerance_check", "final")
graph.add_edge("final", END)
graph = graph.compile()
