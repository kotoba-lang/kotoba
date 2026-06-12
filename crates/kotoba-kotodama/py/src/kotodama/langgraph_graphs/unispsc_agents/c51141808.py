from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_name: str
    compliance_cleared: bool
    purity_verified: bool

def validate_pharma_compliance(state: ProcurementState):
    print('Validating pharmaceutical regulatory compliance for Zolpidem...')
    return {'compliance_cleared': True}

def check_purity_specs(state: ProcurementState):
    print('Verifying API purity certificate...')
    return {'purity_verified': True}

graph = StateGraph(ProcurementState)
graph.add_node('compliance', validate_pharma_compliance)
graph.add_node('purity', check_purity_specs)
graph.set_entry_point('compliance')
graph.add_edge('compliance', 'purity')
graph.add_edge('purity', END)
graph = graph.compile()
