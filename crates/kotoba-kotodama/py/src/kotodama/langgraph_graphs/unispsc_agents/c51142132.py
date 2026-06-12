from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_id: str
    purity_validated: bool
    compliance_checked: bool

def validate_purity(state: ProcurementState):
    # Simulate purity check via CAS registry or lab report
    return {'purity_validated': True}

def verify_compliance(state: ProcurementState):
    # Simulate GMP/Drug registration verification
    return {'compliance_checked': True}

graph = StateGraph(ProcurementState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('verify_compliance', verify_compliance)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'verify_compliance')
graph.add_edge('verify_compliance', END)
graph = graph.compile()
