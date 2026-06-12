from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class HybridizationState(TypedDict):
    spec_data: dict
    validation_log: list
    is_compliant: bool

def validate_filter_specs(state: HybridizationState):
    specs = state.get('spec_data', {})
    log = []
    compliant = True
    if 'pore_size_microns' not in specs:
        log.append('Missing pore size specification.')
        compliant = False
    return {'validation_log': log, 'is_compliant': compliant}

builder = StateGraph(HybridizationState)
builder.add_node('validate', validate_filter_specs)
builder.set_entry_point('validate')
builder.add_edge('validate', END)
graph = builder.compile()
