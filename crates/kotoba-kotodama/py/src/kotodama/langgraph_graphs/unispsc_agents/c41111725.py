from typing import TypedDict
from langgraph.graph import StateGraph, END

class MicroscopeState(TypedDict):
    model_id: str
    calibration_status: bool
    compliance_checked: bool

def validate_specs(state: MicroscopeState):
    state['compliance_checked'] = True
    return state

def verify_calibration(state: MicroscopeState):
    state['calibration_status'] = True
    return state

graph = StateGraph(MicroscopeState)
graph.add_node('validate', validate_specs)
graph.add_node('calibrate', verify_calibration)
graph.set_entry_point('validate')
graph.add_edge('validate', 'calibrate')
graph.add_edge('calibrate', END)
graph = graph.compile()
