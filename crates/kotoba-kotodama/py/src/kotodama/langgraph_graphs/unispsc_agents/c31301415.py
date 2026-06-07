from typing import TypedDict
from langgraph.graph import StateGraph, END

class ForgingState(TypedDict):
    part_specs: dict
    validation_results: dict

def validate_material(state: ForgingState):
    # Business logic for confirming brass alloy composition
    return {'validation_results': {'material_ok': True}}

def check_dimensions(state: ForgingState):
    # Logic for verifying CNC tolerances
    return {'validation_results': {'dims_ok': True}}

graph = StateGraph(ForgingState)
graph.add_node('material_check', validate_material)
graph.add_node('dimension_check', check_dimensions)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'dimension_check')
graph.add_edge('dimension_check', END)
graph = graph.compile()
