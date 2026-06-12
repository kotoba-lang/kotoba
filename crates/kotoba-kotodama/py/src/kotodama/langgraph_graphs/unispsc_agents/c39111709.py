from typing import TypedDict
from langgraph.graph import StateGraph, END

class EmergencyLightState(TypedDict):
    spec_data: dict
    compliance_verified: bool
    approved: bool

def validate_specs(state: EmergencyLightState):
    specs = state.get('spec_data', {})
    # Ensure duration is at least 30 minutes for emergency standards
    duration = specs.get('duration', 0)
    verified = duration >= 30
    return {'compliance_verified': verified}

def decision_node(state: EmergencyLightState):
    return 'approved' if state['compliance_verified'] else 'rejected'

graph = StateGraph(EmergencyLightState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)

graph = graph.compile()
