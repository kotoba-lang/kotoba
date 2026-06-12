from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcureState(TypedDict):
    part_id: str
    material_certified: bool
    export_license_verified: bool
    safety_clearance: bool

def validate_materials(state: ProcureState):
    return {'material_certified': True}

def verify_compliance(state: ProcureState):
    return {'export_license_verified': True}

def final_safety_check(state: ProcureState):
    return {'safety_clearance': True}

graph = StateGraph(ProcureState)
graph.add_node('validate', validate_materials)
graph.add_node('compliance', verify_compliance)
graph.add_node('safety', final_safety_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
