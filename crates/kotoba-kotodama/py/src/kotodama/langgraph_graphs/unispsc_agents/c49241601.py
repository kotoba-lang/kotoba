from typing import TypedDict
from langgraph.graph import StateGraph, END

class CroquetWorkflowState(TypedDict):
    spec_verified: bool
    compliance_checked: bool
    quality_approved: bool

def validate_specs(state: CroquetWorkflowState):
    state['spec_verified'] = True
    return state

def check_standards(state: CroquetWorkflowState):
    state['compliance_checked'] = True
    return state

def approve_quality(state: CroquetWorkflowState):
    state['quality_approved'] = True
    return state

graph = StateGraph(CroquetWorkflowState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_standards)
graph.add_node('quality', approve_quality)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', 'quality')
graph.add_edge('quality', END)
graph = graph.compile()
