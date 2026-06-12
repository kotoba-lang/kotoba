from typing import TypedDict
from langgraph.graph import StateGraph, END

class VitalSignState(TypedDict):
    device_id: str
    calibration_status: bool
    compliance_report: str

def validate_certification(state: VitalSignState):
    state['compliance_report'] = 'Validating ISO 13485 and FDA status'
    return state

def check_calibration(state: VitalSignState):
    state['calibration_status'] = True
    return state

graph = StateGraph(VitalSignState)
graph.add_node('validate', validate_certification)
graph.add_node('calibrate', check_calibration)
graph.set_entry_point('validate')
graph.add_edge('validate', 'calibrate')
graph.add_edge('calibrate', END)
graph = graph.compile()
