from typing import TypedDict, Annotated, List, Union
from langgraph.graph import StateGraph, END

class MiningComponentState(TypedDict):
    component_id: str
    material_cert: bool
    dimension_check: bool
    approved: bool

def validate_material(state: MiningComponentState):
    # Simulate material composition validation
    return {"material_cert": True}

def validate_dimensions(state: MiningComponentState):
    # Simulate geometric tolerance checking
    return {"dimension_check": True}

def final_assembly_check(state: MiningComponentState):
    approved = state.get("material_cert") and state.get("dimension_check")
    return {"approved": approved}

graph = StateGraph(MiningComponentState)
graph.add_node("material", validate_material)
graph.add_node("dimensions", validate_dimensions)
graph.add_node("assembly", final_assembly_check)
graph.add_edge("material", "dimensions")
graph.add_edge("dimensions", "assembly")
graph.add_edge("assembly", END)
graph.set_entry_point("material")
graph = graph.compile()
