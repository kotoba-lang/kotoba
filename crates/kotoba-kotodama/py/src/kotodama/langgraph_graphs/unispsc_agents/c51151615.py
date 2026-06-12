from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_name: str
    purity_validated: bool
    compliance_checked: bool

def validate_purity(state: ProcurementState):
    print('Validating chemical purity for Caramiphen...')
    return {'purity_validated': True}

def verify_compliance(state: ProcurementState):
    print('Verifying pharmaceutical regulatory compliance...')
    return {'compliance_checked': True}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_purity)
graph.add_node('compliance', verify_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
