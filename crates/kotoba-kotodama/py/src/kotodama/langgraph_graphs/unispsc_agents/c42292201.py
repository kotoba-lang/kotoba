from typing import TypedDict
from langgraph.graph import StateGraph, END

class SurgicalState(TypedDict):
    device_id: str
    compliance_validated: bool
    sterility_check: bool

def validate_certification(state: SurgicalState):
    state['compliance_validated'] = True
    return state

def inspect_sterility(state: SurgicalState):
    state['sterility_check'] = True
    return state

graph = StateGraph(SurgicalState)
graph.add_node('cert_check', validate_certification)
graph.add_node('sterility_check', inspect_sterility)
graph.set_entry_point('cert_check')
graph.add_edge('cert_check', 'sterility_check')
graph.add_edge('sterility_check', END)
graph = graph.compile()
