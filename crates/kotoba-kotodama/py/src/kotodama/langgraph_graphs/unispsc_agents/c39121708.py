from langgraph.graph import StateGraph, END
from typing import TypedDict

class RailState(TypedDict):
    material: str
    length_mm: float
    is_compliant: bool

def validate_rail(state: RailState):
    # Basic validation logic for DIN Rail specs
    state['is_compliant'] = state.get('material') in ['Steel', 'Aluminum'] and state.get('length_mm', 0) > 0
    return state

builder = StateGraph(RailState)
builder.add_node('validate', validate_rail)
builder.set_entry_point('validate')
builder.add_edge('validate', END)
graph = builder.compile()
