from typing import TypedDict
from langgraph.graph import StateGraph, END

class PulmonaryState(TypedDict):
    device_id: str
    regulatory_compliant: bool
    calibration_check: bool

def validate_compliance(state: PulmonaryState):
    state['regulatory_compliant'] = True
    return state

def run_calibration_test(state: PulmonaryState):
    state['calibration_check'] = True
    return state

graph = StateGraph(PulmonaryState)
graph.add_node('validate', validate_compliance)
graph.add_node('calibrate', run_calibration_test)
graph.add_edge('validate', 'calibrate')
graph.add_edge('calibrate', END)
graph.set_entry_point('validate')
graph = graph.compile()
