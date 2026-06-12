from typing import TypedDict
from langgraph.graph import StateGraph, END

class VetsurgeryState(TypedDict):
    instrument_type: str
    material_check: bool
    sterilization_validated: bool
    approved: bool

def validate_materials(state: VetsurgeryState):
    # logic for verifying stainless steel grade
    return {"material_check": True}

def validate_sterilization(state: VetsurgeryState):
    # logic for checking autoclave compatibility
    return {"sterilization_validated": True}

further_approval = lambda state: "approved" if state["material_check"] and state["sterilization_validated"] else "rejected"

graph = StateGraph(VetsurgeryState)
graph.add_node("mat_check", validate_materials)
graph.add_node("ster_check", validate_sterilization)
graph.set_entry_point("mat_check")
graph.add_edge("mat_check", "ster_check")
graph.add_edge("ster_check", END)
graph = graph.compile()
