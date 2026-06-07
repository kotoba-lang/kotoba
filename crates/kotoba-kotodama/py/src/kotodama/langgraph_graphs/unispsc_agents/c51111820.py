from typing import TypedDict
from langgraph.graph import StateGraph, END

class LetrozoleState(TypedDict):
    batch_id: str
    compliance_check: bool
    temp_log_verified: bool

def validate_compliance(state: LetrozoleState) -> LetrozoleState:
    state['compliance_check'] = True
    return state

def verify_storage(state: LetrozoleState) -> LetrozoleState:
    state['temp_log_verified'] = True
    return state

graph = StateGraph(LetrozoleState)
graph.add_node('validate', validate_compliance)
graph.add_node('storage', verify_storage)
graph.set_entry_point('validate')
graph.add_edge('validate', 'storage')
graph.add_edge('storage', END)
graph = graph.compile()
