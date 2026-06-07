from typing import TypedDict
from langgraph.graph import StateGraph, END

class InstrumentState(TypedDict):
    device_id: str
    calibration_status: bool
    specs_verified: bool

def validate_specs(state: InstrumentState):
    state['specs_verified'] = True
    return state

def check_calibration(state: InstrumentState):
    state['calibration_status'] = True
    return state

graph = StateGraph(InstrumentState)
graph.add_node('validate', validate_specs)
graph.add_node('calibrate', check_calibration)
graph.set_entry_point('validate')
graph.add_edge('validate', 'calibrate')
graph.add_edge('calibrate', END)
graph = graph.compile()
