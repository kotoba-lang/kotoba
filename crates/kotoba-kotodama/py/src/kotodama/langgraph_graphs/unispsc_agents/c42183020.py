from typing import TypedDict
from langgraph.graph import StateGraph, END

class OphthalmicSpecState(TypedDict):
    device_id: str
    calibration_status: bool
    compliance_verified: bool
    approval_status: str

def validate_specs(state: OphthalmicSpecState):
    state['calibration_status'] = True
    return {'calibration_status': True}

def check_regulatory(state: OphthalmicSpecState):
    state['compliance_verified'] = True
    return {'compliance_verified': True}

graph = StateGraph(OphthalmicSpecState)
graph.add_node('validate', validate_specs)
graph.add_node('regulatory', check_regulatory)
graph.set_entry_point('validate')
graph.add_edge('validate', 'regulatory')
graph.add_edge('regulatory', END)
graph = graph.compile()
