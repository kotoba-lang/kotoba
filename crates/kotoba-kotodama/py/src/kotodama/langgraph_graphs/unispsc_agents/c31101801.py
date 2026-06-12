from typing import TypedDict
from langgraph.graph import StateGraph, END

class CastState(TypedDict):
    material_certified: bool
    dimensional_check_passed: bool
    ndt_verified: bool

def validate_material(state: CastState):
    return {'material_certified': True}

def perform_dimensional_check(state: CastState):
    return {'dimensional_check_passed': True}

def final_inspection(state: CastState):
    return {'ndt_verified': True}

graph = StateGraph(CastState)
graph.add_node('material', validate_material)
graph.add_node('dimensional', perform_dimensional_check)
graph.add_node('ndt', final_inspection)

graph.set_entry_point('material')
graph.add_edge('material', 'dimensional')
graph.add_edge('dimensional', 'ndt')
graph.add_edge('ndt', END)
graph = graph.compile()
