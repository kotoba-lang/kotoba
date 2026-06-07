from langgraph.graph import StateGraph, END
from typing import TypedDict

class SurgicalProcurementState(TypedDict):
    device_id: str
    compliance_cleared: bool
    calibration_passed: bool

def validate_compliance(state: SurgicalProcurementState):
    print('Checking FDA/ISO compliance metrics...')
    state['compliance_cleared'] = True
    return state

def verify_calibration(state: SurgicalProcurementState):
    print('Conducting sensor drift and latency tests...')
    state['calibration_passed'] = True
    return state

graph = StateGraph(SurgicalProcurementState)
graph.add_node('compliance', validate_compliance)
graph.add_node('calibration', verify_calibration)
graph.set_entry_point('compliance')
graph.add_edge('compliance', 'calibration')
graph.add_edge('calibration', END)
graph = graph.compile()
