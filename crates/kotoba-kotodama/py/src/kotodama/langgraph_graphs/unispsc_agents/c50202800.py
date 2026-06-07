from typing import TypedDict
from langgraph.graph import StateGraph, END

class JuiceState(TypedDict):
    brix_value: float
    safety_verified: bool
    approved: bool

def validate_quality(state: JuiceState):
    state['safety_verified'] = state.get('brix_value', 0) > 10
    return state

def approve_procurement(state: JuiceState):
    state['approved'] = state['safety_verified']
    return state

graph = StateGraph(JuiceState)
graph.add_node("validate", validate_quality)
graph.add_node("approve", approve_procurement)
graph.set_entry_point("validate")
graph.add_edge("validate", "approve")
graph.add_edge("approve", END)
graph = graph.compile()
