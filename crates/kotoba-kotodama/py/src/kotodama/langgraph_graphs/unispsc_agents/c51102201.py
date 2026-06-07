from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PharmState(TypedDict):
    purity: float
    reg_compliant: bool
    expiry_check: bool

def validate_compliance(state: PharmState):
    return {"reg_compliant": state.get("purity", 0) >= 99.0}

def check_expiry(state: PharmState):
    return {"expiry_check": True}

graph = StateGraph(PharmState)
graph.add_node("compliance", validate_compliance)
graph.add_node("expiry", check_expiry)
graph.set_entry_point("compliance")
graph.add_edge("compliance", "expiry")
graph.add_edge("expiry", END)
graph = graph.compile()
