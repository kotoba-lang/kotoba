from typing import TypedDict
from langgraph.graph import StateGraph, END

class ControlState(TypedDict):
    console_id: str
    spec_validated: bool
    compliance_score: float

def validate_specs(state: ControlState):
    # Simulate CAD/Spec validation for vehicle consoles
    state['spec_validated'] = True
    return state

def check_compliance(state: ControlState):
    state['compliance_score'] = 0.95
    return state

graph = StateGraph(ControlState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
