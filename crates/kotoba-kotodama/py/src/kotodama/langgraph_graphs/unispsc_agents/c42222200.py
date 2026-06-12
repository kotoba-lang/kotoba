from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    product_id: str
    compliance_docs: list
    validation_status: bool

def validate_medical_device(state: ProcurementState):
    # Basic validation for regulatory docs
    docs = state.get('compliance_docs', [])
    is_valid = 'ISO13485' in docs and 'CE_Mark' in docs
    return {'validation_status': is_valid}

def process_risk_assessment(state: ProcurementState):
    # High value item workflow logic
    return {'validation_status': state['validation_status'] and True}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_medical_device)
graph.add_node('risk_check', process_risk_assessment)
graph.add_edge('validate', 'risk_check')
graph.add_edge('risk_check', END)
graph.set_entry_point('validate')
graph = graph.compile()
