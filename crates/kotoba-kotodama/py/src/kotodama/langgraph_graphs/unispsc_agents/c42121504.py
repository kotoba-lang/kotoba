from typing import TypedDict
from langgraph.graph import StateGraph, END

class StereotaxicState(TypedDict):
    equipment_id: str
    calibration_status: bool
    precision_check: bool
    inspection_passed: bool

def validate_calibration(state: StereotaxicState):
    state['calibration_status'] = True
    return state

def check_precision(state: StereotaxicState):
    state['precision_check'] = True
    return state

def final_approval(state: StereotaxicState):
    state['inspection_passed'] = state['calibration_status'] and state['precision_check']
    return state

graph = StateGraph(StereotaxicState)
graph.add_node('calibrate', validate_calibration)
graph.add_node('precision', check_precision)
graph.add_node('approve', final_approval)
graph.set_entry_point('calibrate')
graph.add_edge('calibrate', 'precision')
graph.add_edge('precision', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
