from typing import TypedDict
from langgraph.graph import StateGraph, END

class DisplayState(TypedDict):
    material: str
    stability_check: bool
    dimensions_ok: bool

def validate_material(state: DisplayState):
    return {'stability_check': state.get('material') in ['ABS', 'Fiberglass', 'Velvet']}

def validate_dimensions(state: DisplayState):
    return {'dimensions_ok': True}

graph = StateGraph(DisplayState)
graph.add_node('validate_material', validate_material)
graph.add_node('validate_dimensions', validate_dimensions)
graph.set_entry_point('validate_material')
graph.add_edge('validate_material', 'validate_dimensions')
graph.add_edge('validate_dimensions', END)
graph = graph.compile()
