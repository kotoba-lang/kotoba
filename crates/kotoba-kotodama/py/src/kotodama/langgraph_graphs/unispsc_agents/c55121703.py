from typing import TypedDict
from langgraph.graph import StateGraph, END

class SignageState(TypedDict):
    spec_data: dict
    is_compliant: bool

def validate_electrical_specs(state: SignageState):
    specs = state.get('spec_data', {})
    # Check for mandatory certification field presence
    compliant = 'Compliance certifications' in specs and specs.get('Input voltage') is not None
    return {'is_compliant': compliant}

def approval_workflow(state: SignageState):
    print('Proceeding to quality inspection' if state['is_compliant'] else 'Flagged for review')
    return state

graph = StateGraph(SignageState)
graph.add_node('validation', validate_electrical_specs)
graph.add_node('approval', approval_workflow)
graph.add_edge('validation', 'approval')
graph.add_edge('approval', END)
graph.set_entry_point('validation')
graph = graph.compile()
