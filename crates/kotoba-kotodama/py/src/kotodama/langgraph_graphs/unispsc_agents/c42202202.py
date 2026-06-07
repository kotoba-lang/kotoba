from typing import TypedDict
from langgraph.graph import StateGraph, END

class RadiosurgeryState(TypedDict):
    device_id: str
    is_calibrated: bool
    shielding_approved: bool
    safety_clearance: bool

def validate_shielding(state: RadiosurgeryState):
    state['shielding_approved'] = True
    return state

def check_calibration(state: RadiosurgeryState):
    state['is_calibrated'] = True
    return state

def verify_safety(state: RadiosurgeryState):
    state['safety_clearance'] = state['shielding_approved'] and state['is_calibrated']
    return state

graph = StateGraph(RadiosurgeryState)
graph.add_node('validate_shielding', validate_shielding)
graph.add_node('check_calibration', check_calibration)
graph.add_node('verify_safety', verify_safety)
graph.set_entry_point('validate_shielding')
graph.add_edge('validate_shielding', 'check_calibration')
graph.add_edge('check_calibration', 'verify_safety')
graph.add_edge('verify_safety', END)
graph = graph.compile()
