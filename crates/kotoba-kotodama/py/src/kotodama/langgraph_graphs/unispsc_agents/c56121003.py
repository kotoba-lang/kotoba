from typing import TypedDict
from langgraph.graph import StateGraph, END

class BookReturnState(TypedDict):
    material_compliance: bool
    dimensions_verified: bool
    final_approval: bool

def validate_material(state: BookReturnState):
    state['material_compliance'] = True
    return state

def check_dimensions(state: BookReturnState):
    state['dimensions_verified'] = True
    return state

def approve(state: BookReturnState):
    state['final_approval'] = True
    return state

graph_builder = StateGraph(BookReturnState)
graph_builder.add_node('validate_material', validate_material)
graph_builder.add_node('check_dimensions', check_dimensions)
graph_builder.add_node('approve', approve)
graph_builder.set_entry_point('validate_material')
graph_builder.add_edge('validate_material', 'check_dimensions')
graph_builder.add_edge('check_dimensions', 'approve')
graph_builder.add_edge('approve', END)
graph = graph_builder.compile()
