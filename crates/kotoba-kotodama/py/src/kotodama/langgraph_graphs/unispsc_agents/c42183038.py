from typing import TypedDict
from langgraph.graph import StateGraph, END

class OphthalmicSupplyState(TypedDict):
    sterilization_checked: bool
    compliance_verified: bool
    is_approved: bool

def validate_sterilization(state: OphthalmicSupplyState):
    return {'sterilization_checked': True}

def verify_medical_compliance(state: OphthalmicSupplyState):
    return {'compliance_verified': True, 'is_approved': True}

builder = StateGraph(OphthalmicSupplyState)
builder.add_node('sterilization', validate_sterilization)
builder.add_node('compliance', verify_medical_compliance)
builder.set_entry_point('sterilization')
builder.add_edge('sterilization', 'compliance')
builder.add_edge('compliance', END)
graph = builder.compile()
