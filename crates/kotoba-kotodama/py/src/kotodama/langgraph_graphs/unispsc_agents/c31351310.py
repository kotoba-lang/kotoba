from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class AssemblyState(TypedDict):
    part_number: str
    material_certified: bool
    inspection_passed: bool
    risk_level: str

def check_material(state: AssemblyState):
    return {'material_certified': True}

def perform_ndt(state: AssemblyState):
    return {'inspection_passed': True}

graph = StateGraph(AssemblyState)
graph.add_node('verify_material', check_material)
graph.add_node('ndt_testing', perform_ndt)
graph.add_edge('verify_material', 'ndt_testing')
graph.add_edge('ndt_testing', END)
graph.set_entry_point('verify_material')
graph = graph.compile()
