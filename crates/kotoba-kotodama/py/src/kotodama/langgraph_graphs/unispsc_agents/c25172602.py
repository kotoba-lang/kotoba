from typing import TypedDict
from langgraph.graph import StateGraph, END

class FenderState(TypedDict):
    part_number: str
    material_certified: bool
    dimensional_check_passed: bool

def validate_materials(state: FenderState):
    # Simulate material compliance check
    return {'material_certified': True}

def validate_dimensions(state: FenderState):
    # Simulate CAD/Dimension validation
    return {'dimensional_check_passed': True}

graph = StateGraph(FenderState)
graph.add_node('material_check', validate_materials)
graph.add_node('dimension_check', validate_dimensions)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'dimension_check')
graph.add_edge('dimension_check', END)

graph = graph.compile()
