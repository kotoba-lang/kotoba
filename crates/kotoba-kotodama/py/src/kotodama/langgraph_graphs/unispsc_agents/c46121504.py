from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class MissileState(TypedDict):
    serial_number: str
    export_license_status: bool
    safety_check_passed: bool
    final_clearance: bool

def validate_export(state: MissileState):
    state['export_license_status'] = True
    return state

def perform_safety_audit(state: MissileState):
    state['safety_check_passed'] = True
    return state

def finalize_clearance(state: MissileState):
    state['final_clearance'] = state['export_license_status'] and state['safety_check_passed']
    return state

graph = StateGraph(MissileState)
graph.add_node('export_review', validate_export)
graph.add_node('safety_audit', perform_safety_audit)
graph.add_node('final_approval', finalize_clearance)
graph.set_entry_point('export_review')
graph.add_edge('export_review', 'safety_audit')
graph.add_edge('safety_audit', 'final_approval')
graph.add_edge('final_approval', END)
graph = graph.compile()
