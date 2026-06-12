from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class LeadProcurementState(TypedDict):
    purity_check: bool
    safety_compliance: bool
    hazardous_shipping_approval: bool

def validate_purity(state: LeadProcurementState):
    return {'purity_check': True}

def verify_safety(state: LeadProcurementState):
    return {'safety_compliance': True}

def process_shipping(state: LeadProcurementState):
    return {'hazardous_shipping_approval': True}

graph = StateGraph(LeadProcurementState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('verify_safety', verify_safety)
graph.add_node('process_shipping', process_shipping)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'verify_safety')
graph.add_edge('verify_safety', 'process_shipping')
graph.add_edge('process_shipping', END)

graph = graph.compile()
