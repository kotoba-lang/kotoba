from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class DisplayAccessoryState(TypedDict):
    accessory_type: str
    spec_check: bool
    compatibility_verified: bool

def validate_specs(state: DisplayAccessoryState):
    state['spec_check'] = True
    return state

def verify_compatibility(state: DisplayAccessoryState):
    state['compatibility_verified'] = True
    return state

graph = StateGraph(DisplayAccessoryState)
graph.add_node('validate', validate_specs)
graph.add_node('verify', verify_compatibility)
graph.set_entry_point('validate')
graph.add_edge('validate', 'verify')
graph.add_edge('verify', END)
graph = graph.compile()
