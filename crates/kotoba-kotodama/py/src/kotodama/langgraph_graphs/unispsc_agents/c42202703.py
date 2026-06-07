from typing import TypedDict
from langgraph.graph import StateGraph, END

class RadiotherapyState(TypedDict):
    device_id: str
    calibration_status: bool
    safety_interlock_check: bool
    approved: bool

def validate_hardware(state: RadiotherapyState):
    # Simulate CAD/Spec validation for radiotherapy components
    state['calibration_status'] = True
    return state

def safety_audit(state: RadiotherapyState):
    # Validate interlock telemetry
    state['safety_interlock_check'] = True
    state['approved'] = state['calibration_status'] and state['safety_interlock_check']
    return state

graph = StateGraph(RadiotherapyState)
graph.add_node('validate', validate_hardware)
graph.add_node('safety', safety_audit)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
