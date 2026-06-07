from typing import TypedDict
from langgraph.graph import StateGraph, END

class PipeState(TypedDict):
    material_certified: bool
    pressure_test_passed: bool
    assembly_verified: bool

def validate_material(state: PipeState):
    state['material_certified'] = True
    return state

def run_pressure_tests(state: PipeState):
    state['pressure_test_passed'] = True
    return state

def verify_assembly(state: PipeState):
    state['assembly_verified'] = True
    return state

graph = StateGraph(PipeState)
graph.add_node('material', validate_material)
graph.add_node('pressure', run_pressure_tests)
graph.add_node('assembly', verify_assembly)
graph.set_entry_point('material')
graph.add_edge('material', 'pressure')
graph.add_edge('pressure', 'assembly')
graph.add_edge('assembly', END)
graph = graph.compile()
