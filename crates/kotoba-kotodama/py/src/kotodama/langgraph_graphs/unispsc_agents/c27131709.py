from typing import TypedDict
from langgraph.graph import StateGraph, END

class CylinderState(TypedDict):
    part_number: str
    material_compliance: bool
    dimensional_check: bool
    approved: bool

def validate_material(state: CylinderState):
    # Simulate material compliance check
    state['material_compliance'] = True
    return state

def validate_dimensions(state: CylinderState):
    # Simulate CAD dimensional validation
    state['dimensional_check'] = True
    return state

def finalize_validation(state: CylinderState):
    state['approved'] = state['material_compliance'] and state['dimensional_check']
    return state

graph = StateGraph(CylinderState)
graph.add_node('material', validate_material)
graph.add_node('dimensions', validate_dimensions)
graph.add_node('finalize', finalize_validation)
graph.set_entry_point('material')
graph.add_edge('material', 'dimensions')
graph.add_edge('dimensions', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
