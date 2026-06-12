from typing import TypedDict
from langgraph.graph import StateGraph, END

class DosimeterState(TypedDict):
    device_id: str
    calibration_status: bool
    compliance_checked: bool

def validate_compliance(state: DosimeterState):
    return {'compliance_checked': True}

def verify_calibration(state: DosimeterState):
    state['calibration_status'] = True
    return state

graph = StateGraph(DosimeterState)
graph.add_node('validate', validate_compliance)
graph.add_node('calibrate', verify_calibration)
graph.set_entry_point('validate')
graph.add_edge('validate', 'calibrate')
graph.add_edge('calibrate', END)
graph = graph.compile()
