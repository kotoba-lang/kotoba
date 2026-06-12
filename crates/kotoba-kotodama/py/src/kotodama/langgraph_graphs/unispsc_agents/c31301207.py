from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class MagnesiumForgingState(TypedDict):
    part_number: str
    material_cert: dict
    mechanical_test: dict
    approved: bool

def validate_dimensional_specs(state: MagnesiumForgingState):
    # Simulate CNC inspection validation
    return {'approved': True}

def check_material_integrity(state: MagnesiumForgingState):
    # Simulate NDT/microstructure analysis
    return {'approved': True}

graph = StateGraph(MagnesiumForgingState)
graph.add_node('material_check', check_material_integrity)
graph.add_node('dimension_check', validate_dimensional_specs)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'dimension_check')
graph.add_edge('dimension_check', END)
graph = graph.compile()
