from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    gmp_verified: bool
    purity_level: float
    status: str

def validate_quality(state: ProcurementState):
    state['gmp_verified'] = state.get('purity_level', 0) >= 99.0
    state['status'] = 'COMPLIANT' if state['gmp_verified'] else 'REJECTED'
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validation', validate_quality)
graph.set_entry_point('validation')
graph.add_edge('validation', END)
graph = graph.compile()
