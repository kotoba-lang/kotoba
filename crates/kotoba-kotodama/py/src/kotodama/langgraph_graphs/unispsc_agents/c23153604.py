from typing import TypedDict
from langgraph.graph import StateGraph, END

class WeldingGraphState(TypedDict):
    equipment_id: str
    calibration_status: bool
    safety_check_passed: bool

def validate_safety(state: WeldingGraphState):
    return {'safety_check_passed': True}

def calibrate_device(state: WeldingGraphState):
    return {'calibration_status': True}

graph = StateGraph(WeldingGraphState)
graph.add_node('safety_check', validate_safety)
graph.add_node('calibration', calibrate_device)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'calibration')
graph.add_edge('calibration', END)
graph = graph.compile()
