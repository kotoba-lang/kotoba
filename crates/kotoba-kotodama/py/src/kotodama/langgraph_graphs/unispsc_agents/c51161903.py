from typing import TypedDict
from langgraph.graph import StateGraph, END

class PharmaState(TypedDict):
    purity_check: bool
    compliance_verified: bool
    status: str

def validate_quality(state: PharmaState):
    state['purity_check'] = True
    return {'status': 'Quality Checked'}

def verify_compliance(state: PharmaState):
    state['compliance_verified'] = True
    return {'status': 'Compliance Verified'}

builder = StateGraph(PharmaState)
builder.add_node('quality_check', validate_quality)
builder.add_node('compliance', verify_compliance)
builder.add_edge('quality_check', 'compliance')
builder.set_entry_point('quality_check')
builder.add_edge('compliance', END)
graph = builder.compile()
