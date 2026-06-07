from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class TobaccoState(TypedDict):
    product_ids: List[str]
    compliance_passed: bool
    tax_cleared: bool

def validate_compliance(state: TobaccoState):
    # Simulate regulatory check
    return {"compliance_passed": True}

def verify_tax(state: TobaccoState):
    # Simulate excise tax verification
    return {"tax_cleared": True}

graph = StateGraph(TobaccoState)
graph.add_node("compliance", validate_compliance)
graph.add_node("tax", verify_tax)
graph.set_entry_point("compliance")
graph.add_edge("compliance", "tax")
graph.add_edge("tax", END)
graph = graph.compile()
