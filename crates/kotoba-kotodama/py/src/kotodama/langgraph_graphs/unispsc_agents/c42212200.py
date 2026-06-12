from typing import TypedDict
from langgraph.graph import StateGraph, END

class MedicationAidState(TypedDict):
    product_id: str
    material_certified: bool
    usability_score: float
    status: str

def validate_materials(state: MedicationAidState):
    return {"material_certified": True}

def evaluate_usability(state: MedicationAidState):
    return {"usability_score": 0.95, "status": "APPROVED"}

graph = StateGraph(MedicationAidState)
graph.add_node("validate_materials", validate_materials)
graph.add_node("evaluate_usability", evaluate_usability)
graph.set_entry_point("validate_materials")
graph.add_edge("validate_materials", "evaluate_usability")
graph.add_edge("evaluate_usability", END)
graph = graph.compile()
