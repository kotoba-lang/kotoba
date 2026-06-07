from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalState(TypedDict):
    material_compliance: bool
    mercury_safety_check: bool
    approved: bool

def check_compliance(state: DentalState):
    return {"material_compliance": True}

def verify_safety(state: DentalState):
    return {"mercury_safety_check": True, "approved": True}

graph = StateGraph(DentalState)
graph.add_node("compliance_check", check_compliance)
graph.add_node("safety_verification", verify_safety)
graph.add_edge("compliance_check", "safety_verification")
graph.add_edge("safety_verification", END)
graph.set_entry_point("compliance_check")
graph = graph.compile()
