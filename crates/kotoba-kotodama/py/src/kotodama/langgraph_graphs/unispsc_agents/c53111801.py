from typing import TypedDict
from langgraph.graph import StateGraph, END

class SandalsState(TypedDict):
    material_compliance: bool
    sizing_check: bool
    approved: bool

def validate_specs(state: SandalsState):
    state['material_compliance'] = True
    return state

def check_sizing(state: SandalsState):
    state['sizing_check'] = True
    return state

def finalize(state: SandalsState):
    state['approved'] = state['material_compliance'] and state['sizing_check']
    return state

graph = StateGraph(SandalsState)
graph.add_node("validate", validate_specs)
graph.add_node("sizing", check_sizing)
graph.add_node("approve", finalize)
graph.set_entry_point("validate")
graph.add_edge("validate", "sizing")
graph.add_edge("sizing", "approve")
graph.add_edge("approve", END)
graph = graph.compile()
