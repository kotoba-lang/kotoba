from typing import TypedDict
from langgraph.graph import StateGraph, END

class ExtrusionState(TypedDict):
    purity: float
    dimensions_ok: bool
    approved: bool

def validate_specs(state: ExtrusionState):
    state['dimensions_ok'] = state.get('purity', 0) > 99.9
    return {'dimensions_ok': state['dimensions_ok']}

def approval_node(state: ExtrusionState):
    state['approved'] = state['dimensions_ok']
    return {'approved': state['approved']}

graph = StateGraph(ExtrusionState)
graph.add_node('validate', validate_specs)
graph.add_node('approve', approval_node)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
