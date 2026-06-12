from typing import TypedDict
from langgraph.graph import StateGraph, END

class SurgicalToolState(TypedDict):
    tool_id: str
    material_certified: bool
    sterilization_verified: bool
    status: str

def validate_material(state: SurgicalToolState):
    return {"material_certified": True, "status": "Material Verified"}

def verify_sterilization(state: SurgicalToolState):
    return {"sterilization_verified": True, "status": "Sterile Process QA Passed"}

graph = StateGraph(SurgicalToolState)
graph.add_node("validate", validate_material)
graph.add_node("sterilize", verify_sterilization)
graph.set_entry_point("validate")
graph.add_edge("validate", "sterilize")
graph.add_edge("sterilize", END)
graph = graph.compile()
