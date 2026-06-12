from typing import TypedDict
from langgraph.graph import StateGraph, END

class ContainerState(TypedDict):
    compliance_checked: bool
    safety_verified: bool
    finalized: bool

def check_compliance(state: ContainerState):
    state['compliance_checked'] = True
    return state

def verify_safety(state: ContainerState):
    state['safety_verified'] = True
    return state

graph = StateGraph(ContainerState)
graph.add_node('compliance', check_compliance)
graph.add_node('safety', verify_safety)
graph.set_entry_point('compliance')
graph.add_edge('compliance', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
