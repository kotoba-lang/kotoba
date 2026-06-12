from typing import TypedDict
from langgraph.graph import StateGraph, END

class AssemblyState(TypedDict):
    assembly_id: str
    material_certified: bool
    pressure_test_passed: bool
    is_validated: bool

def validate_material(state: AssemblyState) -> AssemblyState:
    # Simulate material compliance check
    state['material_certified'] = True
    return state

def test_pressure(state: AssemblyState) -> AssemblyState:
    # Simulate structural integrity testing
    state['pressure_test_passed'] = True
    return state

def finalize_validation(state: AssemblyState) -> AssemblyState:
    state['is_validated'] = state['material_certified'] and state['pressure_test_passed']
    return state

graph = StateGraph(AssemblyState)
graph.add_node('material', validate_material)
graph.add_node('pressure', test_pressure)
graph.add_node('finalize', finalize_validation)
graph.set_entry_point('material')
graph.add_edge('material', 'pressure')
graph.add_edge('pressure', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
