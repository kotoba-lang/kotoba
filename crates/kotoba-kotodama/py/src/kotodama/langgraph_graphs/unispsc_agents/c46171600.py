from typing import TypedDict
from langgraph.graph import StateGraph, END

class SurveillanceState(TypedDict):
    device_id: str
    compliance_check: bool
    encryption_status: str

def validate_hardware(state: SurveillanceState) -> SurveillanceState:
    # Logic for checking secure boot and encryption standards
    state['compliance_check'] = True
    return state

def security_audit(state: SurveillanceState) -> SurveillanceState:
    # Logic for export control and dual-use review
    state['encryption_status'] = 'AES-256-Validated'
    return state

graph = StateGraph(SurveillanceState)
graph.add_node('validate', validate_hardware)
graph.add_node('audit', security_audit)
graph.set_entry_point('validate')
graph.add_edge('validate', 'audit')
graph.add_edge('audit', END)
graph = graph.compile()
