from typing import TypedDict
from langgraph.graph import StateGraph, END

class CameraState(TypedDict):
    resolution: str
    compliance_ok: bool
    approved: bool

def validate_specs(state: CameraState):
    state['compliance_ok'] = state.get('resolution') in ['1080p', '4K']
    return state

def approval_check(state: CameraState):
    state['approved'] = state['compliance_ok']
    return state

graph = StateGraph(CameraState)
graph.add_node('validate', validate_specs)
graph.add_node('approve', approval_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
