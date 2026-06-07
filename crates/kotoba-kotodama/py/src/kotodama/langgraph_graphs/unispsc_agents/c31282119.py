from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class ComponentState(TypedDict):
    dimensions: dict
    material_cert: bool
    is_approved: bool

def validate_specs(state: ComponentState):
    # Simulate CAD/Spec validation for spin-formed parts
    if state.get("dimensions") and state.get("material_cert"):
        return {"is_approved": True}
    return {"is_approved": False}

graph = StateGraph(ComponentState)
graph.add_node("validate", validate_specs)
graph.set_entry_point("validate")
graph.add_edge("validate", END)
graph = graph.compile()
