from typing import TypedDict
from langgraph.graph import StateGraph, END

class PhysicsMaterialState(TypedDict):
    material_id: str
    purity_validated: bool
    compliance_checked: bool

def validate_purity(state: PhysicsMaterialState):
    return {"purity_validated": True}

def check_compliance(state: PhysicsMaterialState):
    return {"compliance_checked": True}

graph = StateGraph(PhysicsMaterialState)
graph.add_node("validate", validate_purity)
graph.add_node("compliance", check_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()
