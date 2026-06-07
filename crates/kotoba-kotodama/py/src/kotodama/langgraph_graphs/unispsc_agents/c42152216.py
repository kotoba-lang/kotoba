from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalSupplyState(TypedDict):
    item_name: str
    safety_verified: bool
    compliance_docs: list

def validate_safety(state: DentalSupplyState):
    return {"safety_verified": True}

def process_compliance(state: DentalSupplyState):
    return {"compliance_docs": ["ISO-13485", "CE-Medical"]}

graph = StateGraph(DentalSupplyState)
graph.add_node("safety_check", validate_safety)
graph.add_node("compliance_registry", process_compliance)
graph.add_edge("safety_check", "compliance_registry")
graph.add_edge("compliance_registry", END)
graph.set_entry_point("safety_check")
graph = graph.compile()
