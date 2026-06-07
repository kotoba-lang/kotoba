from typing import TypedDict
from langgraph.graph import StateGraph, END

class KitchenApplianceState(TypedDict):
    model_number: str
    material_safety: bool
    pressure_test_passed: bool

def validate_material(state: KitchenApplianceState):
    return {"material_safety": True}

def validate_pressure(state: KitchenApplianceState):
    return {"pressure_test_passed": True}

graph = StateGraph(KitchenApplianceState)
graph.add_node("validate_material", validate_material)
graph.add_node("validate_pressure", validate_pressure)
graph.set_entry_point("validate_material")
graph.add_edge("validate_material", "validate_pressure")
graph.add_edge("validate_pressure", END)
graph = graph.compile()
