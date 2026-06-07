from langgraph.graph import StateGraph, END
from typing import TypedDict

class GrilleState(TypedDict):
    part_number: str
    material_certified: bool
    dimensional_check_passed: bool

def validate_materials(state: GrilleState):
    state['material_certified'] = True
    return state

def validate_dimensions(state: GrilleState):
    state['dimensional_check_passed'] = True
    return state

graph = StateGraph(GrilleState)
graph.add_node('material_check', validate_materials)
graph.add_node('dimension_check', validate_dimensions)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'dimension_check')
graph.add_edge('dimension_check', END)
graph = graph.compile()
