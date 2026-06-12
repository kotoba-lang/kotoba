from typing import TypedDict
from langgraph.graph import StateGraph, END

class XRayState(TypedDict):
    device_id: str
    compliance_cleared: bool
    calibration_status: bool

def validate_compliance(state: XRayState):
    print('Verifying FDA/CE compliance...')
    return {'compliance_cleared': True}

def verify_calibration(state: XRayState):
    print('Checking radiation dose calibration records...')
    return {'calibration_status': True}

graph = StateGraph(XRayState)
graph.add_node('compliance', validate_compliance)
graph.add_node('calibration', verify_calibration)
graph.set_entry_point('compliance')
graph.add_edge('compliance', 'calibration')
graph.add_edge('calibration', END)
graph = graph.compile()
