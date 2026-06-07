from typing import TypedDict
from langgraph.graph import StateGraph, END

class ShakerState(TypedDict):
    spec_data: dict
    validation_results: list

def validate_specs(state: ShakerState):
    specs = state.get('spec_data', {})
    results = []
    if specs.get('speed_range_rpm', 0) <= 0:
        results.append('Invalid speed range')
    return {'validation_results': results}

def process_procurement(state: ShakerState):
    print('Processing shaker specs...')
    return {'validation_results': state['validation_results'] + ['Specs validated']}

graph = StateGraph(ShakerState)
graph.add_node('validate', validate_specs)
graph.add_node('process', process_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()
