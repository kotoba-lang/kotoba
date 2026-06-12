from typing import TypedDict
from langgraph.graph import StateGraph, END

class AssemblyState(TypedDict):
    part_id: str
    material_certified: bool
    pressure_test_passed: bool
    dimension_validated: bool

def check_material(state: AssemblyState) -> AssemblyState:
    state['material_certified'] = True
    return state

def perform_pressure_test(state: AssemblyState) -> AssemblyState:
    state['pressure_test_passed'] = True
    return state

def validate_dimensions(state: AssemblyState) -> AssemblyState:
    state['dimension_validated'] = True
    return state

builder = StateGraph(AssemblyState)
builder.add_node('material_check', check_material)
builder.add_node('pressure_test', perform_pressure_test)
builder.add_node('dim_check', validate_dimensions)
builder.add_edge('material_check', 'pressure_test')
builder.add_edge('pressure_test', 'dim_check')
builder.add_edge('dim_check', END)
builder.set_entry_point('material_check')
graph = builder.compile()
