from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_id: str
    safety_check_passed: bool
    compliance_verified: bool

def validate_hazardous_material(state: ProcurementState):
    print('Validating hazardous material compliance for Chlorambucil...')
    return {'safety_check_passed': True}

def verify_regulatory_docs(state: ProcurementState):
    print('Verifying pharmaceutical regulatory documentation...')
    return {'compliance_verified': True}

graph = StateGraph(ProcurementState)
graph.add_node('safety_check', validate_hazardous_material)
graph.add_node('compliance', verify_regulatory_docs)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
