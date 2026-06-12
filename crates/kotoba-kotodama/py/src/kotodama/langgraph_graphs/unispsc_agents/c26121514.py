from typing import TypedDict
from langgraph.graph import StateGraph, END

class WireState(TypedDict):
    specs: dict
    validation_passed: bool

def validate_specs(state: WireState):
    specs = state.get('specs', {})
    # Check for mandatory underground insulation standards
    passed = 'insulation_material' in specs and 'voltage_rating' in specs
    return {'validation_passed': passed}

builder = StateGraph(WireState)
builder.add_node('validation', validate_specs)
builder.set_entry_point('validation')
builder.add_edge('validation', END)
graph = builder.compile()
