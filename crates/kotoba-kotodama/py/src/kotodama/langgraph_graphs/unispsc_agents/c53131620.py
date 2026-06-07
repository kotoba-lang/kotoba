from typing import TypedDict
from langgraph.graph import StateGraph, END

class FragranceState(TypedDict):
    product_sku: str
    safety_assessment: bool
    compliance_score: float

def validate_safety(state: FragranceState):
    # Logic to check alcohol content and IFRA standards
    return {"safety_assessment": True}

def check_compliance(state: FragranceState):
    # Logic to classify DG risk based on alcohol content
    return {"compliance_score": 0.95}

workflow = StateGraph(FragranceState)
workflow.add_node("safety", validate_safety)
workflow.add_node("compliance", check_compliance)
workflow.set_entry_point("safety")
workflow.add_edge("safety", "compliance")
workflow.add_edge("compliance", END)
graph = workflow.compile()
