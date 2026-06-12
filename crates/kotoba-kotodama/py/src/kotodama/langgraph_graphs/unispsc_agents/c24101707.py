from typing import TypedDict
from langgraph.graph import StateGraph, END

class RailState(TypedDict):
    spec_data: dict
    validated: bool
    error_log: list

def validate_specs(state: RailState):
    specs = state.get('spec_data', {})
    errors = []
    if specs.get('load_capacity', 0) <= 0:
        errors.append('Invalid load capacity')
    return {'validated': len(errors) == 0, 'error_log': errors}

def process_procurement(state: RailState):
    return {'validated': True} if state['validated'] else {'validated': False}

builder = StateGraph(RailState)
builder.add_node('validate', validate_specs)
builder.add_node('process', process_procurement)
builder.add_edge('validate', 'process')
builder.add_edge('process', END)
builder.set_entry_point('validate')
graph = builder.compile()
