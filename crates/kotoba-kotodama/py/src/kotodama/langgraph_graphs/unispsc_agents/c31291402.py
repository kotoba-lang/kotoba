from typing import TypedDict
from langgraph.graph import StateGraph, END

class BerylliumState(TypedDict):
    material_certified: bool
    export_license_verified: bool
    physical_inspection_passed: bool

def validate_materials(state: BerylliumState):
    return {'material_certified': True}

def check_export_controls(state: BerylliumState):
    return {'export_license_verified': True}

graph = StateGraph(BerylliumState)
graph.add_node('certify', validate_materials)
graph.add_node('export_check', check_export_controls)
graph.set_entry_point('certify')
graph.add_edge('certify', 'export_check')
graph.add_edge('export_check', END)
graph = graph.compile()
