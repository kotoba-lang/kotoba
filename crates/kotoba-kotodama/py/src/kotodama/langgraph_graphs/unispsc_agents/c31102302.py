from typing import TypedDict
from langgraph.graph import StateGraph, END

class CastState(TypedDict):
    part_id: str
    material_compliance: bool
    dimensional_check: bool

def validate_material(state: CastState):
    # Simulate alloy material verification
    return {'material_compliance': True}

def validate_dimensions(state: CastState):
    # Simulate plaster mold casting tolerance validation
    return {'dimensional_check': True}

graph = StateGraph(CastState)
graph.add_node('material_check', validate_material)
graph.add_node('dimension_check', validate_dimensions)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'dimension_check')
graph.add_edge('dimension_check', END)
graph = graph.compile()
