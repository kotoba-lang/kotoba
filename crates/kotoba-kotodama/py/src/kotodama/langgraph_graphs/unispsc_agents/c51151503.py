from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    drug_name: str
    purity_validated: bool
    compliance_checked: bool

def validate_purity(state: ProcurementState):
    print('Validating Physostigmine purity standards...')
    return {'purity_validated': True}

def check_compliance(state: ProcurementState):
    print('Checking regulatory compliance for controlled pharmaceuticals...')
    return {'compliance_checked': True}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_purity)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
