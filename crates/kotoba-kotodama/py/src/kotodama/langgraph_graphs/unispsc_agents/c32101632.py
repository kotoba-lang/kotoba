from typing import TypedDict
from langgraph.graph import StateGraph, END

class State(TypedDict):
    part_number: str
    spec_check: bool
    compliance_review: bool

def validate_specs(state: State):
    # Simulate CAD/Spec validation for ICs
    return {'spec_check': True}

def check_export_controls(state: State):
    # Check for dual-use export compliance
    return {'compliance_review': True}

graph = StateGraph(State)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_export_controls)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
