from typing import TypedDict
from langgraph.graph import StateGraph, END

class FluidState(TypedDict):
    equipment_id: str
    spec_verified: bool
    compliance_passed: bool

def validate_specs(state: FluidState):
    state['spec_verified'] = True
    return state

def check_compliance(state: FluidState):
    state['compliance_passed'] = True
    return state

graph = StateGraph(FluidState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
