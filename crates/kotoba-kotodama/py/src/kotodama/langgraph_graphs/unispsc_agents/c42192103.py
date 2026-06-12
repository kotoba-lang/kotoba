from typing import TypedDict
from langgraph.graph import StateGraph, END

class ChairState(TypedDict):
    spec_data: dict
    is_compliant: bool

def validate_medical_specs(state: ChairState):
    specs = state.get('spec_data', {})
    required = ['Load Capacity', 'ISO 13485']
    is_compliant = all(key in specs for key in required) and specs.get('Load Capacity', 0) >= 150
    return {'is_compliant': is_compliant}

builder = StateGraph(ChairState)
builder.add_node('spec_validation', validate_medical_specs)
builder.set_entry_point('spec_validation')
builder.add_edge('spec_validation', END)
graph = builder.compile()
