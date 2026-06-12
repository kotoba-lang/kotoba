from typing import TypedDict
from langgraph.graph import StateGraph, END

class BiopsyState(TypedDict):
    device_id: str
    is_sterile: bool
    imaging_compatibility: str
    approval_status: bool

def validate_sterility(state: BiopsyState) -> BiopsyState:
    state['is_sterile'] = True
    return state

def verify_compliance(state: BiopsyState) -> BiopsyState:
    state['approval_status'] = True
    return state

graph = StateGraph(BiopsyState)
graph.add_node('validate', validate_sterility)
graph.add_node('compliance', verify_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
