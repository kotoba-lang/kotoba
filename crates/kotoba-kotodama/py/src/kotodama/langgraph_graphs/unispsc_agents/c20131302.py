from typing import TypedDict
from langgraph.graph import StateGraph, END

class BearingState(TypedDict):
    part_number: str
    spec_check: bool
    load_verified: bool

def validate_specs(state: BearingState):
    # Simulate CAD/spec validation logic
    return {"spec_check": True}

def verify_load(state: BearingState):
    # Simulate load engineering validation
    return {"load_verified": True}

graph = StateGraph(BearingState)
graph.add_node("validate", validate_specs)
graph.add_node("load_check", verify_load)
graph.set_entry_point("validate")
graph.add_edge("validate", "load_check")
graph.add_edge("load_check", END)
graph = graph.compile()
