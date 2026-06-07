from typing import TypedDict
from langgraph.graph import StateGraph, END

class BerylliumState(TypedDict):
    material_certified: bool
    export_license_verified: bool
    inspection_passed: bool

def validate_materials(state: BerylliumState):
    return {'material_certified': True}

def verify_export(state: BerylliumState):
    return {'export_license_verified': True}

def conduct_inspection(state: BerylliumState):
    return {'inspection_passed': True}

graph = StateGraph(BerylliumState)
graph.add_node('validate', validate_materials)
graph.add_node('export_check', verify_export)
graph.add_node('inspection', conduct_inspection)

graph.set_entry_point('validate')
graph.add_edge('validate', 'export_check')
graph.add_edge('export_check', 'inspection')
graph.add_edge('inspection', END)

graph = graph.compile()
