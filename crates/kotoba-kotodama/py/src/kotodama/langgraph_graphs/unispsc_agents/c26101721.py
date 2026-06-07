from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProductState(TypedDict):
    spec_data: dict
    validation_passed: bool

def validate_specs(state: ProductState):
    # Business logic for pulley tolerance and material check
    specs = state.get('spec_data', {})
    is_valid = 'material' in specs and 'tolerance' in specs
    return {'validation_passed': is_valid}

def process_procurement(state: ProductState):
    # Simulate CAD file extraction or supplier verification
    return {'validation_passed': True}

builder = StateGraph(ProductState)
builder.add_node('validation', validate_specs)
builder.add_node('process', process_procurement)
builder.add_edge('validation', 'process')
builder.add_edge('process', END)
builder.set_entry_point('validation')
graph = builder.compile()
