from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalToolState(TypedDict):
    tool_id: str
    material_certified: bool
    sterilization_passed: bool

def validate_material(state: DentalToolState):
    return {"material_certified": True}

def validate_sterilization(state: DentalToolState):
    return {"sterilization_passed": True}

graph = StateGraph(DentalToolState)
graph.add_node("material_check", validate_material)
graph.add_node("sterilization_check", validate_sterilization)
graph.add_edge("material_check", "sterilization_check")
graph.add_edge("sterilization_check", END)
graph.set_entry_point("material_check")
graph = graph.compile()
