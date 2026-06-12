from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalSupplyState(TypedDict):
    material: str
    is_sterile: bool
    compliance_docs: list
    status: str

def validate_sterilization(state: DentalSupplyState):
    is_valid = state.get('is_sterile') is True
    return {'status': 'CERTIFIED' if is_valid else 'REJECTED'}

def process_compliance(state: DentalSupplyState):
    docs = state.get('compliance_docs', [])
    is_compliant = len(docs) >= 2
    return {'status': 'APPROVED' if is_compliant else 'PENDING_DOCS'}

graph = StateGraph(DentalSupplyState)
graph.add_node('verify_sterile', validate_sterilization)
graph.add_node('verify_docs', process_compliance)
graph.set_entry_point('verify_sterile')
graph.add_edge('verify_sterile', 'verify_docs')
graph.add_edge('verify_docs', END)
graph = graph.compile()
