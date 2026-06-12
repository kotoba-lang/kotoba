from typing import TypedDict
from langgraph.graph import StateGraph, END

class TunnelState(TypedDict):
    project_id: str
    safety_clearance: bool
    geological_validation: bool

def validate_geology(state: TunnelState) -> TunnelState:
    state['geological_validation'] = True
    return state

def check_safety(state: TunnelState) -> TunnelState:
    state['safety_clearance'] = True
    return state

graph = StateGraph(TunnelState)
graph.add_node('geology', validate_geology)
graph.add_node('safety', check_safety)
graph.set_entry_point('geology')
graph.add_edge('geology', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
