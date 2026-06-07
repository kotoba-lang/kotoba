from typing import TypedDict
from langgraph.graph import StateGraph, END

class DehydratorState(TypedDict):
    spec_data: dict
    validated: bool
    error: str

def validate_specs(state: DehydratorState):
    specs = state.get('spec_data', {})
    if 'TemperatureControlRange' in specs and 'MedicalDeviceCertification' in specs:
        return {'validated': True}
    return {'validated': False, 'error': 'Missing critical regulatory or thermal specs'}

def process_procurement(state: DehydratorState):
    print('Initiating procurement workflow for Dental Dehydrator...')
    return {'validated': True}

graph = StateGraph(DehydratorState)
graph.add_node('validate', validate_specs)
graph.add_node('process', process_procurement)
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph.set_entry_point('validate')
graph = graph.compile()
