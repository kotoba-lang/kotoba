from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class ForgingState(TypedDict):
    part_number: str
    material_cert: bool
    dimension_check: bool
    passed: bool

def validate_material(state: ForgingState) -> ForgingState:
    state['material_cert'] = True
    return state

def validate_dimensions(state: ForgingState) -> ForgingState:
    state['dimension_check'] = True
    return state

def finalize_inspection(state: ForgingState) -> ForgingState:
    state['passed'] = state['material_cert'] and state['dimension_check']
    return state

graph = StateGraph(ForgingState)
graph.add_node('material_check', validate_material)
graph.add_node('dimension_check', validate_dimensions)
graph.add_node('finalize', finalize_inspection)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'dimension_check')
graph.add_edge('dimension_check', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
