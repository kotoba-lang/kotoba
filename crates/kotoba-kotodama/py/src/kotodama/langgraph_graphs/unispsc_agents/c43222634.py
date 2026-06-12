from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class NetState(TypedDict):
    device_id: str
    config_validated: bool
    security_cleared: bool

def validate_device(state: NetState):
    state['config_validated'] = True
    return state

def check_security(state: NetState):
    state['security_cleared'] = True
    return state

graph = StateGraph(NetState)
graph.add_node('validate', validate_device)
graph.add_node('security', check_security)
graph.set_entry_point('validate')
graph.add_edge('validate', 'security')
graph.add_edge('security', END)
graph = graph.compile()
