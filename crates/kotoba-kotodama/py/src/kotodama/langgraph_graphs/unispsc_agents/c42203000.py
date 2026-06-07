from typing import TypedDict
from langgraph.graph import StateGraph, END

class LinacState(TypedDict):
    device_id: str
    safety_check_passed: bool
    calibration_data: dict

def validate_safety(state: LinacState):
    # Simulate regulatory validation logic for specialized hardware
    state['safety_check_passed'] = True
    return state

def run_calibration(state: LinacState):
    state['calibration_data'] = {'dose_accuracy': '0.99'}
    return state

graph = StateGraph(LinacState)
graph.add_node('safety', validate_safety)
graph.add_node('calibration', run_calibration)
graph.set_entry_point('safety')
graph.add_edge('safety', 'calibration')
graph.add_edge('calibration', END)
graph = graph.compile()
