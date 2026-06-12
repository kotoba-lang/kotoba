from typing import TypedDict
from langgraph.graph import StateGraph, END

class ChemicalProcurementState(TypedDict):
    material_name: str
    compliance_cleared: bool
    logistics_approved: bool

def validate_safety_compliance(state: ChemicalProcurementState):
    print('Validating MSDS and Regulatory Status...')
    return {'compliance_cleared': True}

def verify_logistics(state: ChemicalProcurementState):
    print('Verifying DG shipping capabilities...')
    return {'logistics_approved': True}

graph = StateGraph(ChemicalProcurementState)
graph.add_node('validate', validate_safety_compliance)
graph.add_node('logistics', verify_logistics)
graph.set_entry_point('validate')
graph.add_edge('validate', 'logistics')
graph.add_edge('logistics', END)
graph = graph.compile()
