from typing import TypedDict
from langgraph.graph import StateGraph, END

class PostmortemSupplyState(TypedDict):
    product_id: str
    inspection_status: str
    compliance_verified: bool

def validate_thread_specs(state: PostmortemSupplyState):
    # Simulate CAD/Spec validation logic
    state['compliance_verified'] = True
    state['inspection_status'] = 'verified'
    return state

def finalize_procurement(state: PostmortemSupplyState):
    state['inspection_status'] = 'ready_for_dispatch'
    return state

graph = StateGraph(PostmortemSupplyState)
graph.add_node('validate', validate_thread_specs)
graph.add_node('finalize', finalize_procurement)
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate')
graph = graph.compile()
