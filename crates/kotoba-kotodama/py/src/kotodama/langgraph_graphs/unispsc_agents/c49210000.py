from typing import TypedDict
from langgraph.graph import StateGraph, END

class SportsSpecState(TypedDict):
    item_name: str
    safety_verified: bool
    spec_completed: bool

def validate_specs(state: SportsSpecState):
    state['safety_verified'] = True
    return state

def finalize_order(state: SportsSpecState):
    state['spec_completed'] = True
    return state

graph = StateGraph(SportsSpecState)
graph.add_node("validate", validate_specs)
graph.add_node("finalize", finalize_order)
graph.set_entry_point("validate")
graph.add_edge("validate", "finalize")
graph.add_edge("finalize", END)
graph = graph.compile()
