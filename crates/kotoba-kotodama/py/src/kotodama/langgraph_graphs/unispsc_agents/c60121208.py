from typing import TypedDict
from langgraph.graph import StateGraph, END

class PaintProcurementState(TypedDict):
    product_name: str
    safety_cert_verified: bool
    dermatology_report_attached: bool
    is_approved: bool

def validate_safety_data(state: PaintProcurementState):
    state['safety_cert_verified'] = True
    return state

def check_dermatology_report(state: PaintProcurementState):
    state['dermatology_report_attached'] = True
    return state

def finalize_validation(state: PaintProcurementState):
    state['is_approved'] = state['safety_cert_verified'] and state['dermatology_report_attached']
    return state

graph = StateGraph(PaintProcurementState)
graph.add_node('safety_check', validate_safety_data)
graph.add_node('derma_check', check_dermatology_report)
graph.add_node('finalizer', finalize_validation)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'derma_check')
graph.add_edge('derma_check', 'finalizer')
graph.add_edge('finalizer', END)
graph = graph.compile()
