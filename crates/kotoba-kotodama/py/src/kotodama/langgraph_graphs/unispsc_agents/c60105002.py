from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class RadiationDeviceState(TypedDict):
    device_id: str
    calibration_status: bool
    export_license_required: bool

def validate_calibration(state: RadiationDeviceState):
    state['calibration_status'] = True
    return state

def check_export_compliance(state: RadiationDeviceState):
    state['export_license_required'] = True
    return state

graph = StateGraph(RadiationDeviceState)
graph.add_node('validate', validate_calibration)
graph.add_node('export_check', check_export_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export_check')
graph.add_edge('export_check', END)
graph = graph.compile()
