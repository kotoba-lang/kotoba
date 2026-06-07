from typing import TypedDict
from langgraph.graph import StateGraph, END

class DeviceState(TypedDict):
    device_type: str
    compliance_checked: bool
    performance_verified: bool

def validate_telecom_specs(state: DeviceState):
    state['compliance_checked'] = True
    return {'compliance_checked': True}

def perform_signal_test(state: DeviceState):
    state['performance_verified'] = True
    return {'performance_verified': True}

graph = StateGraph(DeviceState)
graph.add_node("validate", validate_telecom_specs)
graph.add_node("test", perform_signal_test)
graph.set_entry_point("validate")
graph.add_edge("validate", "test")
graph.add_edge("test", END)
graph = graph.compile()
