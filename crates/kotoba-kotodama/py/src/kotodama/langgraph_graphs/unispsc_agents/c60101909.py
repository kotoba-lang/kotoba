from typing import TypedDict
from langgraph.graph import StateGraph, END

class StampState(TypedDict):
    material: str
    is_compliant: bool

def validate_stamp_specs(state: StampState):
    state['is_compliant'] = state.get('material') in ['rubber', 'photopolymer', 'metal']
    return state

def route_by_compliance(state: StampState):
    return 'review' if not state['is_compliant'] else END

graph = StateGraph(StampState)
graph.add_node('validate', validate_stamp_specs)
graph.add_node('review', lambda x: x)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_compliance)
graph.add_edge('review', END)

graph = graph.compile()
