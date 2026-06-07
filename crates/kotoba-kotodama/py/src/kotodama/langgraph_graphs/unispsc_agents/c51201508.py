from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    cold_chain_status: bool
    is_approved: bool

def validate_cold_chain(state: ProcurementState):
    state['cold_chain_status'] = True
    return state

def verify_compliance(state: ProcurementState):
    state['is_approved'] = True if state['cold_chain_status'] else False
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_cold_chain)
graph.add_node('compliance', verify_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
