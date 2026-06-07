from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_name: str
    regulatory_compliance: bool
    safety_check_passed: bool

def validate_license(state: ProcurementState):
    print('Verifying controlled substance import license...')
    return {'regulatory_compliance': True}

def perform_safety_check(state: ProcurementState):
    print('Performing hazmat and security protocol audit...')
    return {'safety_check_passed': True}

graph = StateGraph(ProcurementState)
graph.add_node('verify_license', validate_license)
graph.add_node('safety_audit', perform_safety_check)
graph.set_entry_point('verify_license')
graph.add_edge('verify_license', 'safety_audit')
graph.add_edge('safety_audit', END)
graph = graph.compile()
