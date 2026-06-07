from typing import TypedDict
from langgraph.graph import StateGraph, END

class TransformerHandleState(TypedDict):
    part_id: str
    load_verified: bool
    compliance_checked: bool

def verify_load_capacity(state: TransformerHandleState):
    state['load_verified'] = True
    return state

def check_compliance(state: TransformerHandleState):
    state['compliance_checked'] = True
    return state

graph = StateGraph(TransformerHandleState)
graph.add_node('verify_load', verify_load_capacity)
graph.add_node('check_compliance', check_compliance)
graph.add_edge('verify_load', 'check_compliance')
graph.add_edge('check_compliance', END)
graph.set_entry_point('verify_load')
graph = graph.compile()
