from typing import TypedDict
from langgraph.graph import StateGraph, END

class PharmState(TypedDict):
    batch_id: str
    compliance_check: bool
    temp_log_verified: bool

def validate_compliance(state: PharmState):
    state['compliance_check'] = True
    return state

def verify_storage(state: PharmState):
    state['temp_log_verified'] = True
    return state

graph = StateGraph(PharmState)
graph.add_node('compliance', validate_compliance)
graph.add_node('storage', verify_storage)
graph.set_entry_point('compliance')
graph.add_edge('compliance', 'storage')
graph.add_edge('storage', END)

graph = graph.compile()
