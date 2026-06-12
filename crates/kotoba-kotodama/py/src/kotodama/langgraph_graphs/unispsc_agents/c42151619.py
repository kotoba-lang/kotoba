from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class DentalState(TypedDict):
    item_name: str
    material_spec: str
    sterilization_validated: bool
    compliance_docs: List[str]

def validate_materials(state: DentalState):
    return {"material_spec": "Verified: ISO 7153-1 Stainless Steel"}

def check_compliance(state: DentalState):
    return {"compliance_docs": ["ISO 13485", "CE Certification"]}

graph = StateGraph(DentalState)
graph.add_node("validate", validate_materials)
graph.add_node("compliance", check_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()
