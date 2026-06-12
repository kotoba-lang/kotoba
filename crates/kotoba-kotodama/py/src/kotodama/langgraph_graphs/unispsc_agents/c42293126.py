from typing import TypedDict
from langgraph.graph import StateGraph, END

class SurgicalDeviceState(TypedDict):
    device_id: str
    compliance_checked: bool
    sterilization_validated: bool

def validate_compliance(state: SurgicalDeviceState):
    return {'compliance_checked': True}

def validate_sterilization(state: SurgicalDeviceState):
    return {'sterilization_validated': True}

graph_builder = StateGraph(SurgicalDeviceState)
graph_builder.add_node('compliance', validate_compliance)
graph_builder.add_node('sterilization', validate_sterilization)
graph_builder.set_entry_point('compliance')
graph_builder.add_edge('compliance', 'sterilization')
graph_builder.add_edge('sterilization', END)
graph = graph_builder.compile()
