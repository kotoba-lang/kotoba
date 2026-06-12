from typing import TypedDict
from langgraph.graph import StateGraph, END

class AntitubercularState(TypedDict):
    batch_id: str
    compliance_checked: bool
    temp_log_verified: bool

def validate_compliance(state: AntitubercularState):
    state['compliance_checked'] = True
    return state

def verify_storage(state: AntitubercularState):
    state['temp_log_verified'] = True
    return state

graph = StateGraph(AntitubercularState)
graph.add_node('validate', validate_compliance)
graph.add_node('verify', verify_storage)
graph.set_entry_point('validate')
graph.add_edge('validate', 'verify')
graph.add_edge('verify', END)
graph = graph.compile()
