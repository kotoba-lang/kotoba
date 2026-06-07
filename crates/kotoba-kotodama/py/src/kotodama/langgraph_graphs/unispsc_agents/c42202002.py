from typing import TypedDict
from langgraph.graph import StateGraph, END

class LymphState(TypedDict):
    device_id: str
    compliance_checked: bool
    imaging_calibrated: bool

def validate_medical_device(state: LymphState):
    state['compliance_checked'] = True
    return {'compliance_checked': True}

def calibrate_sensors(state: LymphState):
    state['imaging_calibrated'] = True
    return {'imaging_calibrated': True}

graph = StateGraph(LymphState)
graph.add_node('validate', validate_medical_device)
graph.add_node('calibrate', calibrate_sensors)
graph.add_edge('validate', 'calibrate')
graph.add_edge('calibrate', END)
graph.set_entry_point('validate')
graph = graph.compile()
