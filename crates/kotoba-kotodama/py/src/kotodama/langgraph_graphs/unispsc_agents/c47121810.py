from typing import TypedDict
from langgraph.graph import StateGraph, END

class DispenserState(TypedDict):
    material: str
    dimensions: dict
    is_compliant: bool

def validate_materials(state: DispenserState):
    state['is_compliant'] = state.get('material') in ['ABS', 'Steel', 'Stainless Steel']
    return state

def check_dimensions(state: DispenserState):
    w, h = state.get('dimensions', {}).get('w', 0), state.get('dimensions', {}).get('h', 0)
    if w > 0 and h > 0: state['is_compliant'] = state['is_compliant'] and True
    return state

graph = StateGraph(DispenserState)
graph.add_node('validate_materials', validate_materials)
graph.add_node('check_dimensions', check_dimensions)
graph.set_entry_point('validate_materials')
graph.add_edge('validate_materials', 'check_dimensions')
graph.add_edge('check_dimensions', END)
graph = graph.compile()
