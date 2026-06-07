from typing import TypedDict
from langgraph.graph import StateGraph, END

class ImageProcState(TypedDict):
    equipment_id: str
    compliance_verified: bool
    calibration_status: str

def validate_specs(state: ImageProcState):
    state['compliance_verified'] = True
    return state

def check_calibration(state: ImageProcState):
    state['calibration_status'] = 'PASSED'
    return state

graph = StateGraph(ImageProcState)
graph.add_node('validate', validate_specs)
graph.add_node('calibrate', check_calibration)
graph.set_entry_point('validate')
graph.add_edge('validate', 'calibrate')
graph.add_edge('calibrate', END)
graph = graph.compile()
