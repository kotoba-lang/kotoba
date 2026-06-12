from typing import TypedDict
from langgraph.graph import StateGraph, END

class CastingState(TypedDict):
    material: str
    tolerance_check: bool
    approved: bool

def validate_specs(state: CastingState):
    state['tolerance_check'] = state.get('material') == 'Tin-Alloy'
    return state

def approval_node(state: CastingState):
    state['approved'] = state['tolerance_check']
    return state

graph = StateGraph(CastingState)
graph.add_node('validate', validate_specs)
graph.add_node('approve', approval_node)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')
graph = graph.compile()
