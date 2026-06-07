from typing import TypedDict
from langgraph.graph import StateGraph, END

class EduMaterialState(TypedDict):
    material_type: str
    quality_score: float
    has_safety_cert: bool

def validate_materials(state: EduMaterialState):
    return {"quality_score": 1.0 if state.get("material_type") == "cardstock" else 0.5}

def check_compliance(state: EduMaterialState):
    print(f"Compliance check: {state.get('has_safety_cert')}")
    return {"has_safety_cert": True}

graph = StateGraph(EduMaterialState)
graph.add_node("validate", validate_materials)
graph.add_node("compliance", check_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()
