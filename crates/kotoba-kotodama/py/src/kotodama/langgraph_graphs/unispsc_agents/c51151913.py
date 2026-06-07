from typing import TypedDict
from langgraph.graph import StateGraph, END

class ChemicalProcurementState(TypedDict):
    material_id: str
    compliance_verified: bool
    safety_check_passed: bool

def verify_compliance(state: ChemicalProcurementState):
    return {'compliance_verified': True}

def validate_safety_specs(state: ChemicalProcurementState):
    return {'safety_check_passed': True}

graph = StateGraph(ChemicalProcurementState)
graph.add_node('verify_certs', verify_compliance)
graph.add_node('check_safety', validate_safety_specs)
graph.set_entry_point('verify_certs')
graph.add_edge('verify_certs', 'check_safety')
graph.add_edge('check_safety', END)
graph = graph.compile()
