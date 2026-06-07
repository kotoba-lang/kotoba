from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class FabricationState(TypedDict):
    blueprint_id: str
    material_certified: bool
    tolerance_checked: bool
    compliant: bool

def validate_materials(state: FabricationState):
    print('Verifying material strength and grade...')
    return {'material_certified': True}

def validate_dimensions(state: FabricationState):
    print('Performing dimensional CAD validation...')
    return {'tolerance_checked': True}

def finalize_assembly(state: FabricationState):
    is_ok = state['material_certified'] and state['tolerance_checked']
    return {'compliant': is_ok}

graph = StateGraph(FabricationState)
graph.add_node('material', validate_materials)
graph.add_node('dimension', validate_dimensions)
graph.add_node('final', finalize_assembly)
graph.add_edge('material', 'dimension')
graph.add_edge('dimension', 'final')
graph.add_edge('final', END)
graph.set_entry_point('material')
graph = graph.compile()
