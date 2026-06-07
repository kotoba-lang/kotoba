from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ProcessingState(TypedDict):
    part_id: str
    material_certified: bool
    pressure_test_passed: bool
    is_compliant: bool

def validate_materials(state: ProcessingState) -> dict:
    # Logic to verify aerospace grade titanium specs
    return {'material_certified': True}

def perform_pressure_check(state: ProcessingState) -> dict:
    # Logic for hydrostatic test validation
    return {'pressure_test_passed': True}

def finalize_assembly(state: ProcessingState) -> dict:
    is_valid = state['material_certified'] and state['pressure_test_passed']
    return {'is_compliant': is_valid}

graph = StateGraph(ProcessingState)
graph.add_node('ValidateMaterials', validate_materials)
graph.add_node('PressureTest', perform_pressure_check)
graph.add_node('Finalize', finalize_assembly)
graph.set_entry_point('ValidateMaterials')
graph.add_edge('ValidateMaterials', 'PressureTest')
graph.add_edge('PressureTest', 'Finalize')
graph.add_edge('Finalize', END)
graph = graph.compile()
