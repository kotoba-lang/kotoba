from typing import TypedDict
from langgraph.graph import StateGraph, END

class BellProcurementState(TypedDict):
    material_certified: bool
    sound_test_passed: bool
    is_approved: bool

def validate_material(state: BellProcurementState):
    return {"material_certified": True}

def validate_sound(state: BellProcurementState):
    return {"sound_test_passed": True}

def finalize_procurement(state: BellProcurementState):
    return {"is_approved": state['material_certified'] and state['sound_test_passed']}

graph = StateGraph(BellProcurementState)
graph.add_node("material_check", validate_material)
graph.add_node("sound_check", validate_sound)
graph.add_node("finalize", finalize_procurement)
graph.add_edge("material_check", "sound_check")
graph.add_edge("sound_check", "finalize")
graph.add_edge("finalize", END)
graph.set_entry_point("material_check")
graph = graph.compile()
