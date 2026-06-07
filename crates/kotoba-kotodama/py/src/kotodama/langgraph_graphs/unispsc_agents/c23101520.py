from typing import TypedDict
from langgraph.graph import StateGraph, END

class MachineState(TypedDict):
    serial_number: str
    is_calibrated: bool
    compliance_checked: bool

def validate_specs(state: MachineState):
    state['compliance_checked'] = True
    return state

def run_calibration(state: MachineState):
    state['is_calibrated'] = True
    return state

graph = StateGraph(MachineState)
graph.add_node('validate', validate_specs)
graph.add_node('calibrate', run_calibration)
graph.add_edge('validate', 'calibrate')
graph.add_edge('calibrate', END)
graph.set_entry_point('validate')
graph = graph.compile()
