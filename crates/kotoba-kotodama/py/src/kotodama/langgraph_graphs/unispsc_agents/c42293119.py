from typing import TypedDict
from langgraph.graph import StateGraph, END

class SurgicalDeviceState(TypedDict):
    device_id: str
    compliance_verified: bool
    sterility_check: bool
    is_safe: bool

def check_compliance(state: SurgicalDeviceState):
    state['compliance_verified'] = True
    return {'compliance_verified': True}

def check_sterility(state: SurgicalDeviceState):
    state['sterility_check'] = True
    return {'sterility_check': True}

def validate_retractor(state: SurgicalDeviceState):
    state['is_safe'] = state['compliance_verified'] and state['sterility_check']
    return {'is_safe': state['is_safe']}

graph = StateGraph(SurgicalDeviceState)
graph.add_node('compliance', check_compliance)
graph.add_node('sterility', check_sterility)
graph.add_node('validation', validate_retractor)
graph.add_edge('compliance', 'sterility')
graph.add_edge('sterility', 'validation')
graph.add_edge('validation', END)
graph.set_entry_point('compliance')
graph = graph.compile()
