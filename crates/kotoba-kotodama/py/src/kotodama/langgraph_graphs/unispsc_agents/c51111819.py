from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    temp_compliance: bool
    quality_cleared: bool

def validate_cold_chain(state: ProcurementState):
    # Simulate logic check for temperature requirements of Fulvestrant delivery
    state['temp_compliance'] = True
    return state

def check_quality_certs(state: ProcurementState):
    # Simulate verification of GMP and Certificate of Analysis
    state['quality_cleared'] = True
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate_cold_chain', validate_cold_chain)
graph.add_node('check_quality', check_quality_certs)
graph.set_entry_point('validate_cold_chain')
graph.add_edge('validate_cold_chain', 'check_quality')
graph.add_edge('check_quality', END)
graph = graph.compile()
