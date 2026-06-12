from typing import TypedDict
from langgraph.graph import StateGraph, END

class OrthodonticState(TypedDict):
    material_spec: str
    iso_compliant: bool
    approved: bool

def validate_materials(state: OrthodonticState):
    return {"approved": state.get("iso_compliant") is True}

graph = StateGraph(OrthodonticState)
graph.add_node("validate", validate_materials)
graph.set_entry_point("validate")
graph.add_edge("validate", END)
graph = graph.compile()
