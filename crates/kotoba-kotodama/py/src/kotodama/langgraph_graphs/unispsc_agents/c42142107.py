from typing import TypedDict
from langgraph.graph import StateGraph, END

class TherapySystemState(TypedDict):
    device_id: str
    compliance_verified: bool
    calibration_status: bool

def validate_compliance(state: TherapySystemState):
    state['compliance_verified'] = True
    return {'compliance_verified': True}

def verify_calibration(state: TherapySystemState):
    state['calibration_status'] = True
    return {'calibration_status': True}

graph = StateGraph(TherapySystemState)
graph.add_node('compliance', validate_compliance)
graph.add_node('calibration', verify_calibration)
graph.set_entry_point('compliance')
graph.add_edge('compliance', 'calibration')
graph.add_edge('calibration', END)
graph = graph.compile()
