from langgraph.graph import StateGraph, END
from typing import TypedDict

class EaselState(TypedDict):
    material: str
    stability_check: bool
    approved: bool

def validate_stability(state: EaselState):
    return {'stability_check': True}

def approval_step(state: EaselState):
    return {'approved': state['stability_check']}

graph = StateGraph(EaselState)
graph.add_node('validate', validate_stability)
graph.add_node('approve', approval_step)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
