from typing import TypedDict
from langgraph.graph import StateGraph, END

class SurgicalPackState(TypedDict):
    pack_id: str
    is_sterile: bool
    inspection_passed: bool

def validate_sterility(state: SurgicalPackState):
    return {"is_sterile": True}

def perform_quality_inspection(state: SurgicalPackState):
    return {"inspection_passed": True}

graph = StateGraph(SurgicalPackState)
graph.add_node("validate", validate_sterility)
graph.add_node("inspect", perform_quality_inspection)
graph.set_entry_point("validate")
graph.add_edge("validate", "inspect")
graph.add_edge("inspect", END)
graph = graph.compile()
