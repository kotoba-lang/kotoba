from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material: str
    license_verified: bool
    compliance_cleared: bool
    final_status: str

def verify_license(state: ProcurementState):
    print('Verifying DEA and narcotics distribution license...')
    return {'license_verified': True}

def check_compliance(state: ProcurementState):
    print('Checking controlled substance compliance protocols...')
    return {'compliance_cleared': True}

def finalize_procurement(state: ProcurementState):
    return {'final_status': 'APPROVED' if state['license_verified'] and state['compliance_cleared'] else 'REJECTED'}

graph = StateGraph(ProcurementState)
graph.add_node('verify_license', verify_license)
graph.add_node('check_compliance', check_compliance)
graph.add_node('finalize', finalize_procurement)
graph.set_entry_point('verify_license')
graph.add_edge('verify_license', 'check_compliance')
graph.add_edge('check_compliance', 'finalize')
graph.add_edge('finalize', END)

graph = graph.compile()
