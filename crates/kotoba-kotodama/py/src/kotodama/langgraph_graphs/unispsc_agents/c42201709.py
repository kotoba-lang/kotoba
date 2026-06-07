from langgraph.graph import StateGraph, END
from typing import TypedDict
class UltrasoundState(TypedDict):
    device_id: str
    compliance_cleared: bool
    calibrated: bool

def check_compliance(state: UltrasoundState):
    state['compliance_cleared'] = True
    return state

def verify_calibration(state: UltrasoundState):
    state['calibrated'] = True
    return state

graph = StateGraph(UltrasoundState)
graph.add_node('compliance', check_compliance)
graph.add_node('calibration', verify_calibration)
graph.set_entry_point('compliance')
graph.add_edge('compliance', 'calibration')
graph.add_edge('calibration', END)
graph = graph.compile()
