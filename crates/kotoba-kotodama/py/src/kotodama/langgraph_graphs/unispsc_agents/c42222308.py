from typing import TypedDict
from langgraph.graph import StateGraph, END

class BloodBagState(TypedDict):
    spec_data: dict
    validation_results: list
    is_compliant: bool

def validate_medical_specs(state: BloodBagState):
    specs = state.get('spec_data', {})
    results = []
    if specs.get('sterile') and specs.get('iso_compliance'):
        results.append('Safety check passed')
    state['validation_results'] = results
    state['is_compliant'] = len(results) > 0
    return state

def check_expiry(state: BloodBagState):
    expiry = state.get('spec_data', {}).get('expiry_date')
    state['is_compliant'] = state['is_compliant'] and (expiry is not None)
    return state

graph = StateGraph(BloodBagState)
graph.add_node('validate', validate_medical_specs)
graph.add_node('expiry_check', check_expiry)
graph.set_entry_point('validate')
graph.add_edge('validate', 'expiry_check')
graph.add_edge('expiry_check', END)
graph = graph.compile()
