from typing import TypedDict
from langgraph.graph import StateGraph, END

class TubeAssemblyState(TypedDict):
    material_certified: bool
    pressure_test_passed: bool
    dimensions_verified: bool

def check_materials(state: TubeAssemblyState) -> TubeAssemblyState:
    state['material_certified'] = True
    return state

def verify_specs(state: TubeAssemblyState) -> TubeAssemblyState:
    state['pressure_test_passed'] = True
    state['dimensions_verified'] = True
    return state

graph = StateGraph(TubeAssemblyState)
graph.add_node('material_check', check_materials)
graph.add_node('spec_validation', verify_specs)
graph.add_edge('material_check', 'spec_validation')
graph.add_edge('spec_validation', END)
graph.set_entry_point('material_check')
graph = graph.compile()
