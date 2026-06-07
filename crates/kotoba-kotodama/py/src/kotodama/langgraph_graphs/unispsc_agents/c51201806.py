from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class IgGProcurementState(TypedDict):
    batch_id: str
    temp_log_verified: bool
    gmp_status: str

def validate_cold_chain(state: IgGProcurementState) -> IgGProcurementState:
    state['temp_log_verified'] = True
    return state

def verify_gmp(state: IgGProcurementState) -> IgGProcurementState:
    state['gmp_status'] = 'COMPLIANT'
    return state

graph = StateGraph(IgGProcurementState)
graph.add_node('validate_cold_chain', validate_cold_chain)
graph.add_node('verify_gmp', verify_gmp)
graph.set_entry_point('validate_cold_chain')
graph.add_edge('validate_cold_chain', 'verify_gmp')
graph.add_edge('verify_gmp', END)
graph = graph.compile()
