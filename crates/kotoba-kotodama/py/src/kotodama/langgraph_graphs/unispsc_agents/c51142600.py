from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    product_id: str
    compliance_valid: bool
    regulatory_check: str

def validate_compliance(state: ProcurementState):
    # Simulated logic for stimulant compliance verification
    license_check = state.get('product_id', '').startswith('MED-')
    return {'compliance_valid': license_check, 'regulatory_check': 'PASSED' if license_check else 'FAILED'}

def route_by_compliance(state: ProcurementState):
    return 'compliance_node' if state['compliance_valid'] else END

graph = StateGraph(ProcurementState)
graph.add_node('compliance_node', validate_compliance)
graph.set_entry_point('compliance_node')
graph.add_edge('compliance_node', END)
graph = graph.compile()
