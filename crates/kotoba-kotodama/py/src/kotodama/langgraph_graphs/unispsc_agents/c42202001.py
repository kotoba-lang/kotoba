from typing import TypedDict
from langgraph.graph import StateGraph, END

class CameraState(TypedDict):
    device_id: str
    radiation_safety_verified: bool
    calibration_compliant: bool

def validate_radiation_safety(state: CameraState) -> CameraState:
    # Simulate radiation compliance check
    state['radiation_safety_verified'] = True
    return state

def check_calibration(state: CameraState) -> CameraState:
    # Simulate hardware calibration audit
    state['calibration_compliant'] = True
    return state

graph = StateGraph(CameraState)
graph.add_node('radiation_check', validate_radiation_safety)
graph.add_node('calibration_check', check_calibration)
graph.set_entry_point('radiation_check')
graph.add_edge('radiation_check', 'calibration_check')
graph.add_edge('calibration_check', END)
graph = graph.compile()
