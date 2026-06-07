from typing import TypedDict
from langgraph.graph import StateGraph, END

class BakingMixState(TypedDict):
    product_name: str
    compliance_checked: bool
    batch_integrity: bool

def validate_batch(state: BakingMixState):
    return {"batch_integrity": True}

def check_compliance(state: BakingMixState):
    return {"compliance_checked": True}

graph = StateGraph(BakingMixState)
graph.add_node("validate", validate_batch)
graph.add_node("compliance", check_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()
