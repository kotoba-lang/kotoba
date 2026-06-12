from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_name: str
    compliance_ok: bool
    sterility_verified: bool

def validate_medical_standards(state: ProcurementState):
    # Simulate regulatory validation for medical devices
    state['compliance_ok'] = True
    return state

def verify_sterility(state: ProcurementState):
    # Simulate sterility documentation check
    state['sterility_verified'] = True
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_medical_standards)
graph.add_node('sterility', verify_sterility)
graph.set_entry_point('validate')
graph.add_edge('validate', 'sterility')
graph.add_edge('sterility', END)
graph = graph.compile()
