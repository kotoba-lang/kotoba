from typing import TypedDict
from langgraph.graph import StateGraph, END

class WindowState(TypedDict):
    material: str
    dimensions: dict
    is_compliant: bool

def validate_specs(state: WindowState):
    # Business logic for frame spec validation
    state['is_compliant'] = state.get('material') in ['Aluminum', 'Vinyl', 'Wood']
    return state

builder = StateGraph(WindowState)
builder.add_node('validator', validate_specs)
builder.set_entry_point('validator')
builder.add_edge('validator', END)
graph = builder.compile()
