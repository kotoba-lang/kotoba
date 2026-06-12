from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class UrodynamicState(TypedDict):
    product_id: str
    compliance_checks: List[str]
    is_approved: bool

def validate_medical_compliance(state: UrodynamicState):
    checks = state.get('compliance_checks', [])
    if 'ISO 13485' in checks and 'Sterility Cert' in checks:
        state['is_approved'] = True
    else:
        state['is_approved'] = False
    return state

builder = StateGraph(UrodynamicState)
builder.add_node('compliance', validate_medical_compliance)
builder.set_entry_point('compliance')
builder.add_edge('compliance', END)
graph = builder.compile()
