from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class DinnerwareState(TypedDict):
    material: str
    compliance_docs: List[str]
    approved: bool

def validate_material(state: DinnerwareState):
    # Business logic for food-grade compliance
    is_safe = state.get('material') in ['Ceramic', 'Porcelain', 'Melamine', 'StainlessSteel']
    return {'approved': is_safe}

def check_certifications(state: DinnerwareState):
    # Check for required food safety certifications
    docs = state.get('compliance_docs', [])
    is_certified = len(docs) > 0
    return {'approved': is_certified}

graph = StateGraph(DinnerwareState)
graph.add_node("validate_material", validate_material)
graph.add_node("check_certifications", check_certifications)
graph.set_entry_point("validate_material")
graph.add_edge("validate_material", "check_certifications")
graph.add_edge("check_certifications", END)
graph = graph.compile()
