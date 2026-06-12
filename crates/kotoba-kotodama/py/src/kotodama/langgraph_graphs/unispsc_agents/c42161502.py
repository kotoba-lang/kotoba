from typing import TypedDict
from langgraph.graph import StateGraph, END

class DialysateGraphState(TypedDict):
    device_id: str
    temp_calibration_ok: bool
    safety_cert_verified: bool
    is_approved: bool

def validate_specs(state: DialysateGraphState):
    state['temp_calibration_ok'] = True # Mock logic
    return state

def check_compliance(state: DialysateGraphState):
    state['safety_cert_verified'] = True # Mock logic
    state['is_approved'] = state['temp_calibration_ok'] and state['safety_cert_verified']
    return state

graph = StateGraph(DialysateGraphState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)

graph = graph.compile()
