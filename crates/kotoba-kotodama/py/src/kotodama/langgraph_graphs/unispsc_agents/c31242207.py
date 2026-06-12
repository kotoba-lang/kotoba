from typing import TypedDict
from langgraph.graph import StateGraph, END

class BreadboardState(TypedDict):
    flatness: float
    hole_consistency: bool
    approved: bool

def validate_specs(state: BreadboardState):
    if state.get('flatness', 0) < 0.1:
        return {'approved': True}
    return {'approved': False}

graph = StateGraph(BreadboardState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
