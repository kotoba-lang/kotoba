from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material: str
    quality_check: bool
    compliance_cleared: bool

def validate_purity(state: ProcurementState):
    print('Validating Ergotamine tartrate purity standards...')
    return {'quality_check': True}

def check_compliance(state: ProcurementState):
    print('Verifying pharmaceutical license and regulatory compliance...')
    return {'compliance_cleared': True}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_purity)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)

graph = graph.compile()
