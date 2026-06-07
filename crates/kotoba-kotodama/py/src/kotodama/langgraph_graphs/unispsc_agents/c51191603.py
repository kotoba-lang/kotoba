from typing import TypedDict
from langgraph.graph import StateGraph, END

class TPNState(TypedDict):
    batch_id: str
    sterile_check: bool
    temp_log_verified: bool
    approval_status: str

def validate_sterility(state: TPNState) -> TPNState:
    state['sterile_check'] = True
    return state

def verify_logistics(state: TPNState) -> TPNState:
    state['temp_log_verified'] = True
    return state

def finalize_procurement(state: TPNState) -> TPNState:
    state['approval_status'] = 'APPROVED' if state['sterile_check'] and state['temp_log_verified'] else 'REJECTED'
    return state

graph = StateGraph(TPNState)
graph.add_node('sterile_check', validate_sterility)
graph.add_node('logistics_check', verify_logistics)
graph.add_node('finalizer', finalize_procurement)
graph.set_entry_point('sterile_check')
graph.add_edge('sterile_check', 'logistics_check')
graph.add_edge('logistics_check', 'finalizer')
graph.add_edge('finalizer', END)
graph.add_edge('finalizer', END)
graph = graph.compile()
