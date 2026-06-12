from typing import TypedDict
from langgraph.graph import StateGraph, END

class DepressionMaterialState(TypedDict):
    content_reviewed: bool
    compliance_passed: bool
    final_approval: bool

def validate_clinical_content(state: DepressionMaterialState):
    return {"content_reviewed": True}

def check_compliance(state: DepressionMaterialState):
    return {"compliance_passed": True}

def approve_material(state: DepressionMaterialState):
    return {"final_approval": True}

graph = StateGraph(DepressionMaterialState)
graph.add_node("validate", validate_clinical_content)
graph.add_node("compliance", check_compliance)
graph.add_node("approval", approve_material)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", "approval")
graph.add_edge("approval", END)
graph = graph.compile()
