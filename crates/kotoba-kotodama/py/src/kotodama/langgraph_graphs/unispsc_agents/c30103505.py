from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CoreState(TypedDict):
    material_type: str
    specifications: dict
    is_validated: bool

def validate_specs(state: CoreState):
    specs = state.get('specifications', {})
    required = ['density', 'cell_size']
    valid = all(key in specs for key in required)
    return {'is_validated': valid}

def process_procurement(state: CoreState):
    if state['is_validated']:
        print('Procedure: Initiating procurement for wooden honeycomb.')
    return {'is_validated': True}

builder = StateGraph(CoreState)
builder.add_node('validate', validate_specs)
builder.add_node('process', process_procurement)
builder.add_edge('validate', 'process')
builder.add_edge('process', END)
builder.set_entry_point('validate')
graph = builder.compile()
