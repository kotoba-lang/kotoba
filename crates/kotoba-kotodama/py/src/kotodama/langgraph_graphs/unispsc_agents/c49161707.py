from typing import TypedDict
from langgraph.graph import StateGraph, END

class BatonProcurementState(TypedDict):
    material_certified: bool
    compliance_checked: bool
    is_approved: bool

def validate_materials(state: BatonProcurementState):
    state['material_certified'] = True
    return state

def check_security_compliance(state: BatonProcurementState):
    state['compliance_checked'] = True
    state['is_approved'] = state['material_certified'] and state['compliance_checked']
    return state

graph = StateGraph(BatonProcurementState)
graph.add_node('validate', validate_materials)
graph.add_node('compliance', check_security_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')

graph = graph.compile()
