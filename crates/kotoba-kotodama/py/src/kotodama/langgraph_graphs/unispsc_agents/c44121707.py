from typing import TypedDict
from langgraph.graph import StateGraph, END

class PencilState(TypedDict):
    brand: str
    material_safety_data: bool
    qc_passed: bool

def validate_materials(state: PencilState):
    return {"material_safety_data": True}

def perform_qc(state: PencilState):
    return {"qc_passed": True}

graph = StateGraph(PencilState)
graph.add_node("validate", validate_materials)
graph.add_node("qc", perform_qc)
graph.set_entry_point("validate")
graph.add_edge("validate", "qc")
graph.add_edge("qc", END)
graph = graph.compile()
