from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class BerylliumState(TypedDict):
    part_number: str
    material_certs: bool
    export_license_validated: bool
    final_approval: bool

def validate_compliance(state: BerylliumState):
    state['export_license_validated'] = True
    return state

def verify_certs(state: BerylliumState):
    state['material_certs'] = True
    return state

def approve_procurement(state: BerylliumState):
    state['final_approval'] = state['export_license_validated'] and state['material_certs']
    return state

graph = StateGraph(BerylliumState)
graph.add_node('val_compliance', validate_compliance)
graph.add_node('val_certs', verify_certs)
graph.add_node('approve', approve_procurement)
graph.set_entry_point('val_compliance')
graph.add_edge('val_compliance', 'val_certs')
graph.add_edge('val_certs', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
