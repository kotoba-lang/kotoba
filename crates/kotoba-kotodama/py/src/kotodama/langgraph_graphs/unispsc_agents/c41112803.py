from typing import TypedDict
from langgraph.graph import StateGraph, END

class TachometerState(TypedDict):
    spec_data: dict
    validated: bool
    error: str

def validate_specs(state: TachometerState):
    specs = state.get('spec_data', {})
    is_valid = 'diameter' in specs and 'tolerance' in specs
    return {'validated': is_valid, 'error': None if is_valid else 'Missing mandatory spec fields'}

def process_procurement(state: TachometerState):
    return {'status': 'READY_FOR_RFQ' if state['validated'] else 'REJECTED'}

graph = StateGraph(TachometerState)
graph.add_node('validate', validate_specs)
graph.add_node('process', process_procurement)
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph.set_entry_point('validate')
graph = graph.compile()
