from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_name: str
    compliance_passed: bool
    inspection_required: bool

def validate_material(state: ProcurementState):
    # Simulate food safety material check
    return {"compliance_passed": True}

def check_durability(state: ProcurementState):
    # Simulate stress/heat test requirement check
    return {"inspection_required": True}

graph = StateGraph(ProcurementState)
graph.add_node("validate_material", validate_material)
graph.add_node("check_durability", check_durability)
graph.set_entry_point("validate_material")
graph.add_edge("validate_material", "check_durability")
graph.add_edge("check_durability", END)
graph = graph.compile()
