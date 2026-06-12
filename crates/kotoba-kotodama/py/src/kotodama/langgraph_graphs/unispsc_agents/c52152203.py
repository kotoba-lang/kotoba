from typing import TypedDict
from langgraph.graph import StateGraph, END

class SoapBrushState(TypedDict):
    material_compliance: bool
    bristle_density: int
    dispensing_mechanism_pass: bool

def validate_material(state: SoapBrushState):
    return {"material_compliance": True}

def check_mechanism(state: SoapBrushState):
    return {"dispensing_mechanism_pass": True}

graph = StateGraph(SoapBrushState)
graph.add_node("material_check", validate_material)
graph.add_node("mechanism_check", check_mechanism)
graph.set_entry_point("material_check")
graph.add_edge("material_check", "mechanism_check")
graph.add_edge("mechanism_check", END)
graph = graph.compile()
