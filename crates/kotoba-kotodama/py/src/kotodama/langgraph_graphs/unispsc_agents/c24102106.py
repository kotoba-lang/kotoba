from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class PackagingState(TypedDict):
    equipment_id: str
    spec_check: bool
    safety_verified: bool

def validate_specs(state: PackagingState):
    state['spec_check'] = True
    return state

def verify_safety(state: PackagingState):
    state['safety_verified'] = True
    return state

graph = StateGraph(PackagingState)
graph.add_node('validate', validate_specs)
graph.add_node('safety', verify_safety)
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph.set_entry_point('validate')
graph = graph.compile()
