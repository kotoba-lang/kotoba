from typing import TypedDict
from langgraph.graph import StateGraph, END

class TobaccoState(TypedDict):
    product_id: str
    compliance_passed: bool
    tax_verified: bool

def check_compliance(state: TobaccoState):
    # Simulate age and health compliance check
    return {"compliance_passed": True}

def verify_excise(state: TobaccoState):
    # Simulate tax stamp verification
    return {"tax_verified": True}

graph = StateGraph(TobaccoState)
graph.add_node("compliance", check_compliance)
graph.add_node("tax", verify_excise)
graph.set_entry_point("compliance")
graph.add_edge("compliance", "tax")
graph.add_edge("tax", END)
graph = graph.compile()
