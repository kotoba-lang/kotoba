from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcessingState(TypedDict):
    device_id: str
    spec_compliance: bool
    calibration_status: bool

def validate_specs(state: ProcessingState):
    state['spec_compliance'] = True
    return state

def check_calibration(state: ProcessingState):
    state['calibration_status'] = True
    return state

graph = StateGraph(ProcessingState)
graph.add_node('validate', validate_specs)
graph.add_node('calibrate', check_calibration)
graph.set_entry_point('validate')
graph.add_edge('validate', 'calibrate')
graph.add_edge('calibrate', END)
graph = graph.compile()
