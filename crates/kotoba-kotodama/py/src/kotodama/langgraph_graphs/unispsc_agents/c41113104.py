from langgraph.graph import StateGraph, END
from typing import TypedDict

class ExplosimeterState(TypedDict):
    serial_number: str
    calibration_status: bool
    is_compliant: bool

def validate_certification(state: ExplosimeterState):
    # Simulate logic to verify ATEX/IECEx compliance
    state['is_compliant'] = True
    return state

def run_calibration_check(state: ExplosimeterState):
    # Simulate verification of sensor range
    state['calibration_status'] = True
    return state

graph = StateGraph(ExplosimeterState)
graph.add_node('certify', validate_certification)
graph.add_node('calibrate', run_calibration_check)
graph.add_edge('certify', 'calibrate')
graph.add_edge('calibrate', END)
graph.set_entry_point('certify')
graph = graph.compile()
