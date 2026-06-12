from typing import TypedDict
from langgraph.graph import StateGraph, END

class ClothingState(TypedDict):
    item_name: str
    material_compliance: bool
    safety_check_passed: bool

def validate_materials(state: ClothingState) -> ClothingState:
    state['material_compliance'] = True
    return state

def check_safety_standards(state: ClothingState) -> ClothingState:
    state['safety_check_passed'] = True
    return state

graph = StateGraph(ClothingState)
graph.add_node('validate', validate_materials)
graph.add_node('safety', check_safety_standards)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
