from typing import TypedDict
from langgraph.graph import StateGraph, END

class AerospaceState(TypedDict):
    part_number: str
    compliance_docs: list
    is_verified: bool

def validate_specs(state: AerospaceState):
    # Simulate verification of aerospace calibration docs
    docs = state.get("compliance_docs", [])
    is_valid = len(docs) >= 2
    return {"is_verified": is_valid}

graph = StateGraph(AerospaceState)
graph.add_node("validate", validate_specs)
graph.set_entry_point("validate")
graph.add_edge("validate", END)
graph = graph.compile()
