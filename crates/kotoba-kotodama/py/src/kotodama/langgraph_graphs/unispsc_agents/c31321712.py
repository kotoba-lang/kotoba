from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_certified: bool
    conductivity_passed: bool
    dimensional_check_passed: bool

def validate_materials(state: ProcurementState):
    return {'material_certified': True}

def inspect_assembly(state: ProcurementState):
    return {'conductivity_passed': True, 'dimensional_check_passed': True}

graph = StateGraph(ProcurementState)
graph.add_node('material_validation', validate_materials)
graph.add_node('assembly_inspection', inspect_assembly)
graph.add_edge('material_validation', 'assembly_inspection')
graph.add_edge('assembly_inspection', END)
graph.set_entry_point('material_validation')
graph = graph.compile()
