from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalToolState(TypedDict):
    item_name: str
    material_certified: bool
    sterilization_valid: bool

def validate_material(state: DentalToolState):
    return {"material_certified": True}

def validate_sterilization(state: DentalToolState):
    return {"sterilization_valid": True}

graph = StateGraph(DentalToolState)
graph.add_node("material_check", validate_material)
graph.add_node("sterilization_check", validate_sterilization)
graph.set_entry_point("material_check")
graph.add_edge("material_check", "sterilization_check")
graph.add_edge("sterilization_check", END)
graph = graph.compile()
