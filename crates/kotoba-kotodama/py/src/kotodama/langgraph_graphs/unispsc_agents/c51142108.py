from typing import TypedDict
from langgraph.graph import StateGraph, END

class PharmState(TypedDict):
    purity_check: bool
    compliance_ok: bool
    storage_temp: float

def validate_purity(state: PharmState):
    return {"purity_check": True}

def check_regulations(state: PharmState):
    return {"compliance_ok": True}

graph = StateGraph(PharmState)
graph.add_node("validate", validate_purity)
graph.add_node("compliance", check_regulations)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()
