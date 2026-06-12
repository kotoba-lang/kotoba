from typing import TypedDict
from langgraph.graph import StateGraph, END

class SuctionState(TypedDict):
    spec_data: dict
    is_compliant: bool

def validate_medical_standards(state: SuctionState):
    specs = state.get('spec_data', {})
    # Check for mandatory certification requirement
    valid = specs.get('iso_13485', False) and specs.get('sterile', True)
    return {'is_compliant': valid}

def process_tubings_batch(state: SuctionState):
    print('Processing surgical tubing procurement workflow...')
    return {'is_compliant': True}

graph = StateGraph(SuctionState)
graph.add_node('validate', validate_medical_standards)
graph.add_node('process', process_tubings_batch)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)

graph = graph.compile()
