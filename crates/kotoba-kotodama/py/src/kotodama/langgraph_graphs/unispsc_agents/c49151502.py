from langgraph.graph import StateGraph, END
from typing import TypedDict

class SkiState(TypedDict):
    spec_data: dict
    is_validated: bool

def validate_ski_specs(state: SkiState):
    specs = state.get('spec_data', {})
    required = ['Length', 'BindingCertification']
    valid = all(key in specs for key in required)
    return {'is_validated': valid}

def process_ski_order(state: SkiState):
    print('Processing ski procurement requirements...')
    return {'is_validated': True}

graph = StateGraph(SkiState)
graph.add_node('validation', validate_ski_specs)
graph.add_node('procurement', process_ski_order)
graph.add_edge('validation', 'procurement')
graph.add_edge('procurement', END)
graph.set_entry_point('validation')
graph = graph.compile()
