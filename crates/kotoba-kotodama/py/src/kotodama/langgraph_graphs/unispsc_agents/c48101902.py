from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_name: str
    compliance_docs: List[str]
    is_approved: bool

def validate_material_compliance(state: ProcurementState):
    # Simulate audit of food safety certification
    docs = state.get('compliance_docs', [])
    approved = 'FDA_Compliance_Cert' in docs or 'ISO_22000' in docs
    return {'is_approved': approved}

def route_by_approval(state: ProcurementState):
    return 'approved' if state['is_approved'] else 'rejected'

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_material_compliance)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()
