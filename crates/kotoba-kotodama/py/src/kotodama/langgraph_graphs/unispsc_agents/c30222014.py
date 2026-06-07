from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class AirfieldState(TypedDict):
    project_id: str
    pavement_specs: dict
    is_compliant: bool

def validate_compliance(state: AirfieldState):
    specs = state.get('pavement_specs', {})
    state['is_compliant'] = specs.get('friction_coefficient', 0) > 0.5
    return state

def route_verification(state: AirfieldState):
    return 'valid' if state['is_compliant'] else 'reject'

graph = StateGraph(AirfieldState)
graph.add_node('validate', validate_compliance)
graph.add_edge('validate', END)
graph.set_entry_point('validate')

graph = graph.compile()
