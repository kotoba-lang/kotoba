from typing import TypedDict
from langgraph.graph import StateGraph, END

class AlloyState(TypedDict):
    composition_verified: bool
    dimensions_verified: bool
    compliant: bool

def verify_composition(state: AlloyState):
    return {"composition_verified": True}

def verify_dimensions(state: AlloyState):
    return {"dimensions_verified": True}

def check_compliance(state: AlloyState):
    state["compliant"] = state["composition_verified"] and state["dimensions_verified"]
    return state

graph = StateGraph(AlloyState)
graph.add_node("chem_test", verify_composition)
graph.add_node("dim_test", verify_dimensions)
graph.add_node("compliance", check_compliance)
graph.set_entry_point("chem_test")
graph.add_edge("chem_test", "dim_test")
graph.add_edge("dim_test", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()
