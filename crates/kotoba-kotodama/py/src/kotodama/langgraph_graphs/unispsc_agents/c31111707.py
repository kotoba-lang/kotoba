from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class LeadProcurementState(TypedDict):
    material_spec: dict
    compliance_check: bool
    safety_clearance: bool

def validate_lead_specs(state: LeadProcurementState):
    spec = state.get('material_spec', {})
    is_valid = spec.get('purity', 0) >= 99.9
    return {'compliance_check': is_valid}

def safety_protocol_check(state: LeadProcurementState):
    return {'safety_clearance': state.get('compliance_check', False)}

graph = StateGraph(LeadProcurementState)
graph.add_node('validate', validate_lead_specs)
graph.add_node('safety', safety_protocol_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
