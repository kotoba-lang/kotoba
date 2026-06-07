from typing import TypedDict
from langgraph.graph import StateGraph, END

class DrainageProcurementState(TypedDict):
    product_id: str
    is_sterile: bool
    compliance_docs: list
    validation_stage: str

def validate_sterility(state: DrainageProcurementState):
    if state.get('is_sterile'):
        return {'validation_stage': 'verified'}
    return {'validation_stage': 'rejected'}

def check_compliance(state: DrainageProcurementState):
    if len(state.get('compliance_docs', [])) >= 3:
        return {'validation_stage': 'approved'}
    return {'validation_stage': 'review_needed'}

graph = StateGraph(DrainageProcurementState)
graph.add_node('sterility_check', validate_sterility)
graph.add_node('compliance_check', check_compliance)
graph.set_entry_point('sterility_check')
graph.add_edge('sterility_check', 'compliance_check')
graph.add_edge('compliance_check', END)
graph = graph.compile()
