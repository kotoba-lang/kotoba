from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class PotState(TypedDict):
    material: str
    dimensions: dict
    needs_drainage: bool
    is_verified: bool

def validate_specs(state: PotState):
    # Basic validation logic for decorative pots
    state['is_verified'] = state.get('material') is not None and 'dimensions' in state
    return state

builder = StateGraph(PotState)
builder.add_node('validate', validate_specs)
builder.set_entry_point('validate')
builder.add_edge('validate', END)
graph = builder.compile()
