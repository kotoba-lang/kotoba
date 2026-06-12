from typing import TypedDict
from langgraph.graph import StateGraph, END

class AngioscopeState(TypedDict):
    device_id: str
    compliance_checked: bool
    imaging_valid: bool

def validate_specs(state: AngioscopeState):
    # Simulate regulatory validation
    state['compliance_checked'] = True
    return state

def verify_imaging(state: AngioscopeState):
    # Simulate sensitivity verification
    state['imaging_valid'] = True
    return state

graph = StateGraph(AngioscopeState)
graph.add_node('validate', validate_specs)
graph.add_node('imaging', verify_imaging)
graph.set_entry_point('validate')
graph.add_edge('validate', 'imaging')
graph.add_edge('imaging', END)
graph = graph.compile()
