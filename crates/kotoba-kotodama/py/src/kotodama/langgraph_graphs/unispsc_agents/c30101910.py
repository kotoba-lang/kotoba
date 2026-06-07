from typing import TypedDict
from langgraph.graph import StateGraph, END

class BrassProcessingState(TypedDict):
    spec_data: dict
    validation_passed: bool

def validate_brass_specs(state: BrassProcessingState):
    specs = state.get('spec_data', {})
    required = ['alloy_grade', 'thickness']
    passed = all(k in specs for k in required)
    return {'validation_passed': passed}

def route_by_validation(state: BrassProcessingState):
    return 'process' if state['validation_passed'] else END

builder = StateGraph(BrassProcessingState)
builder.add_node('validate', validate_brass_specs)
builder.add_node('process', lambda s: s)
builder.set_entry_point('validate')
builder.add_conditional_edges('validate', route_by_validation)
builder.add_edge('process', END)
graph = builder.compile()
