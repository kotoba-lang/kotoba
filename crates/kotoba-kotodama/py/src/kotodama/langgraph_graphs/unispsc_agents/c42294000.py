from typing import TypedDict
from langgraph.graph import StateGraph, END

class SurgicalToolState(TypedDict):
    tool_id: str
    material_certified: bool
    sterilization_passed: bool

def validate_material(state: SurgicalToolState):
    return {"material_certified": True}

def perform_inspection(state: SurgicalToolState):
    return {"sterilization_passed": True}

graph = StateGraph(SurgicalToolState)
graph.add_node("validate", validate_material)
graph.add_node("inspect", perform_inspection)
graph.add_edge("validate", "inspect")
graph.add_edge("inspect", END)
graph.set_entry_point("validate")
graph = graph.compile()
