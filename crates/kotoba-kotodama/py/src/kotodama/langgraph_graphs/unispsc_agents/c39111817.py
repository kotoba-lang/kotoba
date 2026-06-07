from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class ProcurementState(TypedDict):
    part_number: str
    spec_check: bool
    compliance_verified: bool
    final_approval: bool

def validate_material(state: ProcurementState):
    state['spec_check'] = True
    return state

def check_compliance(state: ProcurementState):
    state['compliance_verified'] = True
    return state

def approve(state: ProcurementState):
    state['final_approval'] = True
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate_material', validate_material)
graph.add_node('check_compliance', check_compliance)
graph.add_node('approve', approve)
graph.set_entry_point('validate_material')
graph.add_edge('validate_material', 'check_compliance')
graph.add_edge('check_compliance', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
