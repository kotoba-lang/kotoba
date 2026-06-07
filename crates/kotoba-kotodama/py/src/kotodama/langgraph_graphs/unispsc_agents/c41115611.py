from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcessingState(TypedDict):
    device_id: str
    calibration_status: bool
    validation_score: float

def check_calibration(state: ProcessingState) -> ProcessingState:
    state['calibration_status'] = True
    return state

def validate_sensor(state: ProcessingState) -> ProcessingState:
    state['validation_score'] = 0.95
    return state

graph = StateGraph(ProcessingState)
graph.add_node('check', check_calibration)
graph.add_node('validate', validate_sensor)
graph.add_edge('check', 'validate')
graph.add_edge('validate', END)
graph.set_entry_point('check')
graph = graph.compile()
