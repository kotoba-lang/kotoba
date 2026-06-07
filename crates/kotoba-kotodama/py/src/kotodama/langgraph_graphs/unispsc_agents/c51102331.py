from typing import TypedDict
from langgraph.graph import StateGraph, END

class SaquinavirState(TypedDict):
    batch_id: str
    gmp_certified: bool
    temp_log_verified: bool
    status: str

def validate_gmp(state: SaquinavirState):
    state['gmp_certified'] = True
    return state

def verify_storage(state: SaquinavirState):
    state['temp_log_verified'] = True
    return state

def finalize_batch(state: SaquinavirState):
    state['status'] = 'APPROVED' if state['gmp_certified'] and state['temp_log_verified'] else 'REJECTED'
    return state

graph = StateGraph(SaquinavirState)
graph.add_node('validate_gmp', validate_gmp)
graph.add_node('verify_storage', verify_storage)
graph.add_node('finalize', finalize_batch)
graph.set_entry_point('validate_gmp')
graph.add_edge('validate_gmp', 'verify_storage')
graph.add_edge('verify_storage', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
