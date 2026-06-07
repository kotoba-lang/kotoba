from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class BinderState(TypedDict):
    item_code: str
    material_certified: bool
    capacity_validated: bool
    is_compliant: bool

def validate_material(state: BinderState):
    # Simulate material compliance check
    return {"material_certified": True}

def validate_capacity(state: BinderState):
    # Simulate capacity constraint check
    return {"capacity_validated": True}

def finalize_check(state: BinderState):
    compliant = state.get("material_certified", False) and state.get("capacity_validated", False)
    return {"is_compliant": compliant}

graph = StateGraph(BinderState)
graph.add_node("validate_material", validate_material)
graph.add_node("validate_capacity", validate_capacity)
graph.add_node("finalize", finalize_check)
graph.set_entry_point("validate_material")
graph.add_edge("validate_material", "validate_capacity")
graph.add_edge("validate_capacity", "finalize")
graph.add_edge("finalize", END)
graph = graph.compile()
