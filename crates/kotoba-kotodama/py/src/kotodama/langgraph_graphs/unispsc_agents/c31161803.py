from typing import TypedDict
from langgraph.graph import StateGraph, END

class WasherState(TypedDict):
    spec_data: dict
    validated: bool

def validate_material(state: WasherState) -> WasherState:
    material = state.get('spec_data', {}).get('material')
    state['validated'] = material in ['stainless_steel', 'carbon_steel', 'brass']
    return state

def check_dimensions(state: WasherState) -> WasherState:
    if state['validated']:
        tol = state.get('spec_data', {}).get('tolerance', 0.05)
        state['validated'] = tol <= 0.1
    return state

builder = StateGraph(WasherState)
builder.add_node('material_check', validate_material)
builder.add_node('dimension_check', check_dimensions)
builder.add_edge('material_check', 'dimension_check')
builder.add_edge('dimension_check', END)
builder.set_entry_point('material_check')
graph = builder.compile()
