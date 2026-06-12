from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    drug_name: str
    compliance_check: bool
    temp_log_verified: bool

def validate_license(state: ProcurementState):
    state['compliance_check'] = True
    return state

def verify_cold_chain(state: ProcurementState):
    state['temp_log_verified'] = True
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate_license', validate_license)
graph.add_node('verify_cold_chain', verify_cold_chain)
graph.add_edge('validate_license', 'verify_cold_chain')
graph.add_edge('verify_cold_chain', END)
graph.set_entry_point('validate_license')
graph = graph.compile()
