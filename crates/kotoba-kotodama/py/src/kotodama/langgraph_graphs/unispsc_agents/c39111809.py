from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class FilterState(TypedDict):
    spec_sheet: dict
    validation_passed: bool
    errors: List[str]

def validate_specs(state: FilterState):
    specs = state.get('spec_sheet', {})
    errors = []
    if not specs.get('transmission_range'):
        errors.append('Missing transmission range')
    return {'validation_passed': len(errors) == 0, 'errors': errors}

builder = StateGraph(FilterState)
builder.add_node('validate', validate_specs)
builder.set_entry_point('validate')
builder.add_edge('validate', END)
graph = builder.compile()
