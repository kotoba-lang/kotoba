from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class MedicalComponentState(TypedDict):
    part_number: str
    iso_compliant: bool
    sterility_verified: bool
    approval_status: str

def validate_iso_compliance(state: MedicalComponentState):
    # Simulate regulatory validation logic for IV/Arterial components
    state['iso_compliant'] = True
    return state

def check_sterility(state: MedicalComponentState):
    # Verify sterility documentation
    state['sterility_verified'] = True
    return state

builder = StateGraph(MedicalComponentState)
builder.add_node('iso_check', validate_iso_compliance)
builder.add_node('sterility_check', check_sterility)
builder.set_entry_point('iso_check')
builder.add_edge('iso_check', 'sterility_check')
builder.add_edge('sterility_check', END)
graph = builder.compile()
