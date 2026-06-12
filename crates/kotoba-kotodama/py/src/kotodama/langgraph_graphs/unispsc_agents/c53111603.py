from typing import TypedDict
from langgraph.graph import StateGraph, END

class ShoeState(TypedDict):
    spec_data: dict
    validation_passed: bool

def validate_materials(state: ShoeState):
    # Simulate material composition validation
    passed = 'chemical_safety' in state.get('spec_data', {})
    return {'validation_passed': passed}

builder = StateGraph(ShoeState)
builder.add_node('validate', validate_materials)
builder.set_entry_point('validate')
builder.add_edge('validate', END)
graph = builder.compile()
