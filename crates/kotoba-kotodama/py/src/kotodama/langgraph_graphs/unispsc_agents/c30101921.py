from typing import TypedDict
from langgraph.graph import StateGraph, END

class CoilState(TypedDict):
    material_compliance: bool
    dimension_check: bool
    final_approval: bool

def validate_material(state: CoilState) -> CoilState:
    state['material_compliance'] = True
    return state

def validate_dimensions(state: CoilState) -> CoilState:
    state['dimension_check'] = True
    return state

builder = StateGraph(CoilState)
builder.add_node('material', validate_material)
builder.add_node('dimensions', validate_dimensions)
builder.add_edge('material', 'dimensions')
builder.add_edge('dimensions', END)
builder.set_entry_point('material')
graph = builder.compile()
