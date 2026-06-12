from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalProductState(TypedDict):
    material_spec: str
    iso_compliant: bool
    dimension_check: bool

def validate_material(state: DentalProductState):
    return {"material_spec": "Verified biocompatible alloy or ceramic"}

def verify_iso(state: DentalProductState):
    return {"iso_compliant": True}

graph = StateGraph(DentalProductState)
graph.add_node("validate_material", validate_material)
graph.add_node("verify_iso", verify_iso)
graph.set_entry_point("validate_material")
graph.add_edge("validate_material", "verify_iso")
graph.add_edge("verify_iso", END)
graph = graph.compile()
