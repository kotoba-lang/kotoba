from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    assembly_id: str
    material_certified: bool
    welding_inspected: bool
    export_cleared: bool

def validate_material(state: ProcurementState):
    return {'material_certified': True}

def inspect_welds(state: ProcurementState):
    return {'welding_inspected': True}

def verify_export(state: ProcurementState):
    return {'export_cleared': True}

graph = StateGraph(ProcurementState)
graph.add_node('material_check', validate_material)
graph.add_node('weld_inspection', inspect_welds)
graph.add_node('export_compliance', verify_export)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'weld_inspection')
graph.add_edge('weld_inspection', 'export_compliance')
graph.add_edge('export_compliance', END)
graph = graph.compile()
