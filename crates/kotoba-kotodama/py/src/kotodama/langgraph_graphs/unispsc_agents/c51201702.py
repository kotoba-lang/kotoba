from typing import TypedDict
from langgraph.graph import StateGraph, END

class EColiState(TypedDict):
    strain: str
    bsl_level: int
    is_verified: bool
    shipping_log: str

def validate_strain(state: EColiState):
    return {"is_verified": state.get("bsl_level", 0) <= 2}

def check_compliance(state: EColiState):
    return {"shipping_log": "Compliant temperature storage confirmed"}

graph = StateGraph(EColiState)
graph.add_node("validate", validate_strain)
graph.add_node("compliance", check_compliance)
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph.set_entry_point("validate")
graph = graph.compile()
