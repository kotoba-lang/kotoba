from typing import TypedDict
from langgraph.graph import StateGraph, END

class CVPState(TypedDict):
    device_id: str
    compliance_checked: bool
    calibration_status: str

def validate_compliance(state: CVPState):
    # Simulate regulatory validation logic for medical device procurement
    state['compliance_checked'] = True
    return state

def check_calibration(state: CVPState):
    state['calibration_status'] = 'VERIFIED'
    return state

graph = StateGraph(CVPState)
graph.add_node('validate', validate_compliance)
graph.add_node('calibrate', check_calibration)
graph.set_entry_point('validate')
graph.add_edge('validate', 'calibrate')
graph.add_edge('calibrate', END)
graph = graph.compile()
