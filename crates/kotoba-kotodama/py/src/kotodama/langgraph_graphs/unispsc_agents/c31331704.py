from typing import TypedDict
from langgraph.graph import StateGraph, END

class AssemblyState(TypedDict):
    part_number: str
    material_certified: bool
    inspection_passed: bool
    status: str

def validate_materials(state: AssemblyState):
    return {'material_certified': True}

def perform_ndt_check(state: AssemblyState):
    return {'inspection_passed': True, 'status': 'Verified'}

graph = StateGraph(AssemblyState)
graph.add_node('material_check', validate_materials)
graph.add_node('ndt_inspection', perform_ndt_check)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'ndt_inspection')
graph.add_edge('ndt_inspection', END)
graph = graph.compile()
