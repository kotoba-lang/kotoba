from typing import TypedDict
from langgraph.graph import StateGraph, END

class NeonState(TypedDict):
    spec_completed: bool
    safety_cleared: bool

def validate_transformer(state: NeonState) -> NeonState:
    state['safety_cleared'] = True
    return state

def verify_specs(state: NeonState) -> NeonState:
    state['spec_completed'] = True
    return state

graph = StateGraph(NeonState)
graph.add_node("validate_transformer", validate_transformer)
graph.add_node("verify_specs", verify_specs)
graph.set_entry_point("validate_transformer")
graph.add_edge("validate_transformer", "verify_specs")
graph.add_edge("verify_specs", END)
graph = graph.compile()
