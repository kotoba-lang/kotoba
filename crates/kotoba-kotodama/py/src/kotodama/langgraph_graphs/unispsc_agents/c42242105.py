from typing import TypedDict
from langgraph.graph import StateGraph, END

class TractionCartState(TypedDict):
    spec_data: dict
    is_compliant: bool

def validate_medical_specs(state: TractionCartState):
    specs = state.get('spec_data', {})
    required = ['load_capacity', 'iso_certification']
    is_valid = all(key in specs for key in required)
    return {'is_compliant': is_valid}

def route_by_compliance(state: TractionCartState):
    return 'process' if state['is_compliant'] else 'reject'

graph = StateGraph(TractionCartState)
graph.add_node('validate', validate_medical_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)

graph = graph.compile()
