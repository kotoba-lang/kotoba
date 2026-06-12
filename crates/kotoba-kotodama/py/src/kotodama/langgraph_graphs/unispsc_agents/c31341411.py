from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class AssemblyState(TypedDict):
    part_id: str
    material_check: bool
    weld_integrity: bool
    export_cleared: bool

def validate_materials(state: AssemblyState):
    return {'material_check': True}

def inspect_sonic_weld(state: AssemblyState):
    return {'weld_integrity': True}

def check_export_compliance(state: AssemblyState):
    return {'export_cleared': True}

graph = StateGraph(AssemblyState)
graph.add_node('material_validation', validate_materials)
graph.add_node('weld_inspection', inspect_sonic_weld)
graph.add_node('export_compliance', check_export_compliance)
graph.set_entry_point('material_validation')
graph.add_edge('material_validation', 'weld_inspection')
graph.add_edge('weld_inspection', 'export_compliance')
graph.add_edge('export_compliance', END)
graph = graph.compile()
