from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    purity_check: bool
    regulatory_approved: bool

def validate_batch(state: ProcurementState):
    return {"purity_check": True}

def check_regulations(state: ProcurementState):
    return {"regulatory_approved": True}

graph = StateGraph(ProcurementState)
graph.add_node("validate", validate_batch)
graph.add_node("compliance", check_regulations)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()
